#!/bin/sh
# Scan staged git changes for secrets and blocked env files.
# Used by pre-commit; run manually with: make check-secrets

set -eu

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

STAGED_FILES="$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)"
if [ -z "$STAGED_FILES" ]; then
  exit 0
fi

FAIL=0

report() {
  echo "secret-scan: $1" >&2
  FAIL=1
}

is_blocked_file() {
  file="$1"
  case "$file" in
    .env|.env.local|.env.production|.env.development|.env.test)
      return 0 ;;
    .env.*)
      case "$file" in .env.example) return 1 ;; *) return 0 ;; esac
      ;;
    *.pem|*.p12|*.pfx|id_rsa|id_rsa.pub|id_ed25519|credentials.json|secrets.json|*.key)
      return 0 ;;
  esac
  return 1
}

is_placeholder() {
  value="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    ""|admin|change-me-local-dev-key|change-me|your-key|your_key|example|placeholder|replace-me|insert-key-here|sk-test|gsk-test|google-test|test-secret-key|test-secret|ollama)
      return 0 ;;
  esac
  case "$1" in
    *change-me*|*your-key*|*your_key*|*example*|*placeholder*|*replace-me*)
      return 0 ;;
  esac
  return 1
}

scan_added_line() {
  file="$1"
  content="$2"

  if printf '%s' "$content" | grep -qE 'BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY'; then
    report "possible private key in $file"
    return 0
  fi

  if printf '%s' "$content" | grep -qE 'sk-[A-Za-z0-9]{20,}'; then
    case "$file" in tests/*) return 0 ;; esac
    report "OpenAI-style API key pattern in $file"
  fi

  if printf '%s' "$content" | grep -qE 'gsk_[A-Za-z0-9]{20,}'; then
    case "$file" in tests/*) return 0 ;; esac
    report "Groq API key pattern in $file"
  fi

  if printf '%s' "$content" | grep -qE 'AIzaSy[A-Za-z0-9_-]{20,}'; then
    report "Google API key pattern in $file"
  fi

  if printf '%s' "$content" | grep -qE 'AKIA[0-9A-Z]{16}'; then
    report "AWS access key pattern in $file"
  fi

  if printf '%s' "$content" | grep -qE 'ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}'; then
    report "GitHub token pattern in $file"
  fi

  for name in DOCINTEL_API_KEYS DOCINTEL_API_KEY DOCINTEL_LLM_API_KEY DOCINTEL_WEBHOOK_SECRET \
    GROQ_API_KEY OPENAI_API_KEY GEMINI_API_KEY GOOGLE_API_KEY \
    AWS_SECRET_ACCESS_KEY AWS_ACCESS_KEY_ID; do
    case "$content" in
      ${name}=*)
        value="${content#${name}=}"
        value="$(printf '%s' "$value" | sed 's/#.*//' | tr -d ' "' | tr -d "'")"
        if [ -n "$value" ] && ! is_placeholder "$value" && [ "${#value}" -ge 12 ]; then
          report "non-placeholder value for $name in $file"
        fi
        ;;
    esac
  done
}

for file in $STAGED_FILES; do
  if is_blocked_file "$file"; then
    report "blocked file staged: $file (secrets belong in .env, which is gitignored)"
  fi
done

LINES_FILE="$(mktemp "${TMPDIR:-/tmp}/docintel-secret-scan.XXXXXX")"
trap 'rm -f "$LINES_FILE"' EXIT HUP INT TERM

git diff --cached -U0 --no-color 2>/dev/null | awk '
  /^\+{3} b\// { sub(/^\+{3} b\//, "", $0); file=$0; next }
  /^@@/ { next }
  /^---/ { next }
  /^\+/ {
    line=substr($0, 2)
    printf "%s\t%s\n", file, line
  }
' > "$LINES_FILE"

while IFS="$(printf '\t')" read -r file line; do
  [ -n "$file" ] || continue
  scan_added_line "$file" "$line"
done < "$LINES_FILE"

if [ "$FAIL" -ne 0 ]; then
  echo "secret-scan: commit blocked. Store real keys in .env only (never commit .env)." >&2
  exit 1
fi

exit 0
