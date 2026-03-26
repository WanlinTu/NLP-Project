"""
Merge LoRA adapter into base model and save in 5GB shards.
Avoids OOM during save by splitting the output into smaller files.

Usage:
    python3 merge_lora_sharded.py
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from pathlib import Path

MERGED_DIR = Path("models/sentiment_merged_opus")

if MERGED_DIR.exists():
    import shutil
    print(f"Removing old {MERGED_DIR}...")
    shutil.rmtree(MERGED_DIR)

MERGED_DIR.mkdir(parents=True, exist_ok=True)

print("Loading base model in fp16 on CPU...")
model = AutoModelForCausalLM.from_pretrained(
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
    torch_dtype=torch.float16,
    device_map="cpu",
    trust_remote_code=True,
)

print("Loading LoRA adapter...")
model = PeftModel.from_pretrained(model, "models/sentiment_lora_opus")

print("Merging LoRA weights into base model...")
model = model.merge_and_unload()

print("Saving in 5GB shards...")
model.save_pretrained(str(MERGED_DIR), max_shard_size="5GB")

print("Saving tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
    trust_remote_code=True,
)
tokenizer.save_pretrained(str(MERGED_DIR))

del model
print("Done.")
print(f"Files: {[f.name for f in MERGED_DIR.iterdir()]}")
