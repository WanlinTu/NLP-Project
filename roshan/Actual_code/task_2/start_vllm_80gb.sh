#!/bin/bash
# Start vLLM on A100 80GB GPU — full optimization.
#
# Request the GPU first:
#   salloc -A p_dsi_acc -p batch_gpu --gres=gpu:nvidia_a100_80gb:1 --mem=64G --time=08:00:00
#
# Then run from task_2/ directory:
#   cd asset/fillings/roshan/Actual_code/task_2
#   bash start_vllm_80gb.sh
#
# Also set MAX_CONCURRENT = 64 in the notebook.

apptainer exec --nv \
  --bind /nobackup/user/$USER:/nobackup/user/$USER \
  --bind /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem:/tmp/ca.pem \
  --bind $PWD:/workspace \
  --env SSL_CERT_FILE=/tmp/ca.pem \
  --env REQUESTS_CA_BUNDLE=/tmp/ca.pem \
  --env HF_HOME=/nobackup/user/$USER/hf \
  --env HUGGINGFACE_HUB_CACHE=/nobackup/user/$USER/hf \
  --env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  /nobackup/user/$USER/containers/vllm.sif \
python3 -m vllm.entrypoints.openai.api_server \
  --model /workspace/models/sentiment_merged_opus/ \
  --tokenizer deepseek-ai/DeepSeek-R1-Distill-Qwen-14B \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.95 \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 2048 \
  --max-num-seqs 128 \
  --max-num-batched-tokens 16384 \
  --enable-prefix-caching \
  --disable-log-requests \
  --trust-remote-code
