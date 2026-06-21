#!/bin/sh
set -eu

OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
MODEL="${OLLAMA_PULL_MODEL:-llama3.2}"

echo "Waiting for Ollama at ${OLLAMA_HOST}..."
until curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; do
  sleep 2
done

echo "Pulling model ${MODEL}..."
curl -sf "${OLLAMA_HOST}/api/pull" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"${MODEL}\"}"

echo "Ollama model ${MODEL} is ready."
