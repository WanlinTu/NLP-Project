# ACCRE Local LLM Deployment — Full Session Handoff

## Goal

Run open-source LLMs locally on **ACCRE GPUs** and expose them through an **OpenAI-compatible API** so existing notebooks can use:

```python
OpenAI(base_url="http://127.0.0.1:8000/v1")
```

instead of OpenAI cloud APIs.

---

# 1. Initial Objective

User wanted:

* Local OSS model
* GPU inference on ACCRE
* GUI notebook interaction
* Persistent model storage
* OpenAI API compatibility
* Zero re-download between sessions

Primary model chosen initially:

```
openai/gpt-oss-20b
```

---

# 2. Key ACCRE Constraints Discovered

## Login Node Limitation

Login node:

```
gw01
```

Cannot:

* access GPUs
* run CUDA
* launch vLLM inference

✅ Models must run inside:

* GPU Jupyter session
* OR `salloc` GPU job

---

## Storage Constraints

Home directory unsuitable for models.

Correct persistent storage:

```
/nobackup/user/$USER/
```

Created directories:

```
/nobackup/user/$USER/containers
/nobackup/user/$USER/hf
/nobackup/user/$USER/logs
```

Purpose:

| Folder     | Purpose                 |
| ---------- | ----------------------- |
| containers | Apptainer images        |
| hf         | HuggingFace model cache |
| logs       | runtime logs            |

---

# 3. Container Setup

Pulled official vLLM container:

```bash
apptainer pull vllm.sif docker://vllm/vllm-openai:latest
```

Result:

```
/nobackup/user/$USER/containers/vllm.sif
(~7.9GB)
```

Important:
Container reused for **all models**.

---

# 4. GPU Session Strategy

Initial SLURM configs failed due to:

```
QOSGrpGRES policy violation
```

Resolved by using:

✅ GPU Type:

```
RTX A6000
```

Working configuration:

* account: `p_dsi_acc`
* partition: batch_gpu / OnDemand GPU session

---

# 5. First Major Failure — Python Not Found

Error:

```
FATAL: "python": executable file not found
```

Cause:
Container exposes `python3`, not `python`.

Fix:

```
python3 -m vllm.entrypoints.openai.api_server
```

---

# 6. TLS Certificate Failure

Error:

```
Could not find a suitable TLS CA certificate bundle
```

Cause:
Apptainer container cannot see host SSL certs.

Fallback implemented:

```bash
--bind /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem:/tmp/ca.pem
--env SSL_CERT_FILE=/tmp/ca.pem
--env REQUESTS_CA_BUNDLE=/tmp/ca.pem
```

Reason:
Allows HuggingFace downloads inside container.

---

# 7. Read-Only Filesystem Failure

Error:

```
OSError: Read-only file system: '/nobackup'
```

Cause:
Apptainer isolation layer.

Critical Fix:

```bash
--bind /nobackup/user/$USER:/nobackup/user/$USER
```

This enabled model downloads.

---

# 8. GPT-OSS-20B Deployment (SUCCESS)

Server launched:

```
http://0.0.0.0:8000
```

Verified endpoints:

```
/v1/models
/v1/chat/completions
```

Test:

```bash
curl /v1/chat/completions
```

Returned:

```
OK
```

Inference confirmed operational.

---

# 9. Architecture Achieved

```
HF Model Cache
        ↓
Apptainer (vLLM)
        ↓
Local OpenAI API
        ↓
Notebook Cells
```

Notebook never interacts with model directly.

---

# 10. Persistence Behavior

Important discovery:

✅ Model downloads persist across sessions.

Models stored at:

```
/nobackup/user/$USER/hf/models--*
```

Restarting session:

* DOES NOT re-download weights
* Only reloads into GPU memory

---

# 11. Known Model Limitation

Observed issue:

```
GPT-OSS-20B performs poorly at tool calling
```

Affected:

* factor extraction notebook cells
* structured outputs

Fallback logic previously added in notebook
to prevent pipeline failure when extraction fails.

---

# 12. Model Replacement Decision

Chosen replacement:

```
Qwen/Qwen3-30B-A3B-Instruct
```

Reasoning:

| Property      | Result |
| ------------- | ------ |
| Reasoning     | Strong |
| Tool calling  | Good   |
| Active params | ~3B    |
| Total params  | 30B    |
| Fits A6000    | ✅      |
| Efficiency    | High   |

Mixture-of-Experts architecture.

---

# 13. Removing GPT-OSS

Deleted locally cached weights:

```bash
rm -rf /nobackup/user/$USER/hf/models--openai--gpt-oss-20b
```

Container NOT deleted.

---

# 14. Qwen Launch Failure

Error:

```
Failed to infer device type
No CUDA runtime found
```

Cause:
Attempted launch from login node.

Resolution:
➡ Must start inside GPU session again.

---

# 15. Final Correct Launch Pattern

Inside GPU Jupyter terminal:

```bash
export HF_HOME=/nobackup/user/$USER/hf
export HUGGINGFACE_HUB_CACHE=$HF_HOME
```

Run:

```bash
apptainer exec --nv \
  --bind /nobackup/user/$USER:/nobackup/user/$USER \
  --bind /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem:/tmp/ca.pem \
  --env SSL_CERT_FILE=/tmp/ca.pem \
  --env REQUESTS_CA_BUNDLE=/tmp/ca.pem \
  --env HF_HOME=/nobackup/user/$USER/hf \
  --env HUGGINGFACE_HUB_CACHE=/nobackup/user/$USER/hf \
  /nobackup/user/$USER/containers/vllm.sif \
python3 -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-30B-A3B-Instruct \
  --dtype bfloat16 \
  --host 0.0.0.0 \
  --port 8000
```

---

# 16. Port + API

Local endpoint:

```
http://127.0.0.1:8000/v1
```

Notebook client:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="local"
)
```

---

# 17. Operational Rules (Critical)

### ALWAYS

* launch GPU session first
* verify `nvidia-smi`
* keep server terminal alive

### NEVER

* run from login node
* download manually
* store models in `$HOME`

---

# 18. Session Restart Procedure

After new ACCRE session:

1. Start GPU Jupyter
2. Open terminal
3. Run vLLM command
4. Wait for model load
5. Run notebooks

No re-download occurs.

---

# 19. Current State

✅ vLLM container ready
✅ Persistent HF cache configured
✅ OpenAI-compatible endpoint working
✅ GPT-OSS removed
✅ Switching to Qwen3-30B-A3B

System ready for continued experimentation.

---

# END OF HANDOFF
