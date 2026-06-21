#!/bin/sh
set -eu

OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
MODEL="${OLLAMA_PULL_MODEL:-llama3.2}"

echo "Waiting for Ollama at ${OLLAMA_HOST}..."
until curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; do
  sleep 2
done

if curl -sf "${OLLAMA_HOST}/api/tags" | grep -F "\"name\":\"${MODEL}\"" >/dev/null 2>&1; then
  echo "Model ${MODEL} is already present. Skipping pull."
  exit 0
fi

if curl -sf "${OLLAMA_HOST}/api/tags" | grep -F "${MODEL}" >/dev/null 2>&1; then
  echo "Model ${MODEL} is already present. Skipping pull."
  exit 0
fi

echo "Pulling model ${MODEL}..."
curl -sf "${OLLAMA_HOST}/api/pull" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"${MODEL}\"}"

echo "Ollama model ${MODEL} is ready."
