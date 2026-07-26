"""
SLM SFT Training Script using Unsloth & HuggingFace TRL
Finetunes Qwen-2.5-7B / 14B or Llama-3.1-8B models on captured user interaction trajectories.
"""

import os
import torch

def train_orchestrator_slm(
    dataset_path: str = "sft_trajectories.jsonl",
    base_model_name: str = "unsloth/Qwen2.5-7B-Instruct",
    output_dir: str = "./qwen_orchestrator_7b",
    max_seq_length: int = 4096,
    batch_size: int = 2,
    learning_rate: float = 2e-4,
    max_steps: int = 300
):
    try:
        from unsloth import FastLanguageModel
        from datasets import load_dataset
        from trl import SFTTrainer
        from transformers import TrainingArguments
    except ImportError:
        print("[Warning] Unsloth or TRL not installed in local environment. Run `pip install unsloth trl transformers` to execute fine-tuning.")
        return

    print(f"[Training] Loading base model: {base_model_name}")
    
    # 1. Load Base Model in 4-bit QLoRA
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model_name,
        max_seq_length=max_seq_length,
        load_in_4bit=True
    )

    # 2. Configure PEFT (LoRA) Adapters
    model = FastLanguageModel.get_peft_model(
        model,
        r=64,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=128,
        lora_dropout=0,
        bias="none",
    )

    # 3. Load Dataset
    dataset = load_dataset("json", data_files={"train": dataset_path})

    # 4. Training Arguments
    training_args = TrainingArguments(
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        warmup_steps=10,
        max_steps=max_steps,
        learning_rate=learning_rate,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        output_dir=output_dir,
    )

    # 5. Trainer Initialization
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        dataset_text_field="messages",
        max_seq_length=max_seq_length,
        dataset_num_proc=2,
        packing=False,
        args=training_args,
    )

    print("[Training] Starting SFT Fine-Tuning loop...")
    trainer.train()

    print(f"[Training] Saving merged weights to {output_dir}_merged")
    model.save_pretrained_merged(f"{output_dir}_merged", tokenizer, save_method="merged_16bit")
    print("[Training] Complete!")

if __name__ == "__main__":
    train_orchestrator_slm()
