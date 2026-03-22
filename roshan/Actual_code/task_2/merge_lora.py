"""
Merge LoRA adapter into base model and save as a standalone model.

Run from terminal (NOT Jupyter) to avoid proxy timeouts:
    cd roshan/Actual_code/task_2
    python3 merge_lora.py

Output: models/sentiment_merged/
Once saved, serve with vLLM:
    vllm serve models/sentiment_merged/ --dtype auto --gpu-memory-utilization 0.90 --max-model-len 2048 --port 8000
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from pathlib import Path

MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B"
LORA_DIR = Path("models/sentiment_lora")
MERGED_DIR = Path("models/sentiment_merged")

if MERGED_DIR.exists() and (MERGED_DIR / "config.json").exists():
    print(f"Merged model already exists at {MERGED_DIR}, nothing to do.")
    exit(0)

assert LORA_DIR.exists(), f"LoRA adapter not found: {LORA_DIR}"

print(f"Loading base model in fp16 on CPU (uses system RAM, not GPU)...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float16,
    device_map="cpu",
    trust_remote_code=True,
)

print(f"Loading LoRA adapter from {LORA_DIR}...")
model = PeftModel.from_pretrained(model, str(LORA_DIR))

print("Merging LoRA weights into base model...")
model = model.merge_and_unload()

MERGED_DIR.mkdir(parents=True, exist_ok=True)
print(f"Saving merged model to {MERGED_DIR}...")
model.save_pretrained(str(MERGED_DIR))

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
tokenizer.save_pretrained(str(MERGED_DIR))

del model
print("Done. Merged model saved.")
print(f"Files: {[f.name for f in MERGED_DIR.iterdir()]}")
