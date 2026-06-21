#!/bin/sh
# Seed an empty Ollama volume from baked models, then start the server.
set -eu

BAKED_DIR="/opt/docintel-ollama-baked"
TARGET_DIR="/root/.ollama"

if [ -d "$BAKED_DIR" ]; then
  mkdir -p "$TARGET_DIR"
  if [ ! -d "${TARGET_DIR}/models" ] || [ -z "$(ls -A "${TARGET_DIR}/models" 2>/dev/null)" ]; then
    echo "Seeding Ollama data from baked image..."
    cp -a "${BAKED_DIR}/." "${TARGET_DIR}/"
  fi
fi

exec ollama serve
