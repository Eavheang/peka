#!/bin/sh
set -eu

config=/config/config.yaml

value() {
  sed -n "s/^$1:[[:space:]]*//p" "$config" | sed -n '1p' | tr -d '\r'
}

exec /app/llama-server \
  --model "/models/$(value model)" \
  --ctx-size "$(value context_size)" \
  --n-gpu-layers "$(value gpu_layers)" \
  --batch-size "$(value batch_size)" \
  --ubatch-size "$(value ubatch_size)" \
  --temp "$(value temperature)" \
  --top-p "$(value top_p)" \
  --min-p "$(value min_p)" \
  --repeat-penalty "$(value repeat_penalty)" \
  --host 0.0.0.0 \
  --port 8080
