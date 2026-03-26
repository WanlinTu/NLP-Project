#!/bin/bash
# Start vLLM serving the Opus-trained merged SFT model.
#
# Usage (from ACCRE home directory):
#   cd asset/fillings/roshan/Actual_code/task_2
#   bash start_vllm.sh
#
# IMPORTANT: Must be run from the task_2/ directory (uses $PWD for bind mount)

apptainer exec --nv \
  --bind /nobackup/user/$USER:/nobackup/user/$USER \
  --bind /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem:/tmp/ca.pem \
  --bind $PWD:/workspace \
  --env SSL_CERT_FILE=/tmp/ca.pem \
  --env REQUESTS_CA_BUNDLE=/tmp/ca.pem \
  --env HF_HOME=/nobackup/user/$USER/hf \
  --env HUGGINGFACE_HUB_CACHE=/nobackup/user/$USER/hf \
  /nobackup/user/$USER/containers/vllm.sif \
python3 -m vllm.entrypoints.openai.api_server \
  --model /workspace/models/sentiment_merged_opus/ \
  --tokenizer deepseek-ai/DeepSeek-R1-Distill-Qwen-14B \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.95 \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 2048 \
  --enable-prefix-caching \
  --disable-log-requests \
  --max-num-seqs 256 \
  --max-num-batched-tokens 16384 \
  --trust-remote-code
