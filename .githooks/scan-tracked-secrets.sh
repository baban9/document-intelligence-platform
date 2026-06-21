#!/bin/sh
# Scan all tracked files for committed secrets (CI and make check-secrets).

set -eu

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

FAIL=0

report() {
  echo "secret-scan: $1" >&2
  FAIL=1
}

if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  report ".env is tracked by git; remove it from the index"
fi

PATTERN='sk-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}|AIzaSy[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY'

while IFS= read -r file; do
  case "$file" in
    tests/*|*.png|*.jpg|*.pdf|*.zip|*.whl) continue ;;
    .env.example) continue ;;
  esac
  if grep -qE "$PATTERN" "$file" 2>/dev/null; then
    report "suspicious secret pattern in tracked file: $file"
  fi
done <<EOF
$(git ls-files)
EOF

if [ "$FAIL" -ne 0 ]; then
  exit 1
fi

exit 0
