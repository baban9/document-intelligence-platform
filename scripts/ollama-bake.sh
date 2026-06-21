#!/bin/sh
# Bake an Ollama model into the image at build time (used by Dockerfile.ollama).
set -eu

MODEL="${OLLAMA_PULL_MODEL:-llama3.2}"

echo "Starting temporary Ollama server for model bake..."
ollama serve &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true' EXIT

ready=0
for _ in $(seq 1 90); do
  if ollama list >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [ "$ready" -ne 1 ]; then
  echo "Ollama server did not become ready during image build." >&2
  exit 1
fi

echo "Pulling ${MODEL} into image layers..."
ollama pull "${MODEL}"
ollama list
echo "Model ${MODEL} baked successfully."
