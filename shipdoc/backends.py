"""Model backends: generate(prompt, image paths, max_tokens) -> (text, stats).

`mlx` runs on Apple Silicon (the official numbers). `hf` runs the same model and prompts through
transformers on CUDA or CPU, so the pipeline reproduces without a Mac (PLAN.md B7).
"""
import time

DEFAULT_MODEL = "mlx-community/Qwen3-VL-8B-Instruct-8bit"


class MLX:
    def __init__(self, model=DEFAULT_MODEL):
        from mlx_vlm import load
        from mlx_vlm.utils import load_config
        self.name = model
        self.model, self.processor = load(model)
        self.config = load_config(model)

    def generate(self, prompt, images, max_tokens):
        import mlx.core as mx
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template
        mx.reset_peak_memory()
        t = time.time()
        chat = apply_chat_template(self.processor, self.config, prompt, num_images=len(images))
        r = generate(self.model, self.processor, chat, image=images, max_tokens=max_tokens, temperature=0.0, verbose=False)
        return r.text, {"secs": round(time.time() - t, 1), "prompt_tokens": r.prompt_tokens,
                        "generation_tokens": r.generation_tokens, "peak_gb": round(mx.get_peak_memory() / 1e9, 2),
                        "finish_reason": r.finish_reason}


def hf_name(model):
    """MLX repo -> the original Hugging Face weights: mlx-community/Qwen3-VL-8B-Instruct-8bit -> Qwen/Qwen3-VL-8B-Instruct."""
    if not model.startswith("mlx-community/"):
        return model
    base = model.split("/")[1]
    for suffix in ("-8bit", "-4bit", "-bf16", "-6bit"):
        base = base.removesuffix(suffix)
    return "Qwen/" + base


class HF:
    """Same model and prompts through transformers, for graders without a Mac.

    Runs the unquantised BF16 weights (8B: ~17 GB, fits a 24 GB GPU; on CPU it needs that much RAM and
    is slow). The official numbers come from MLX 8-bit, so small differences are expected.
    """

    def __init__(self, model=DEFAULT_MODEL, device=None):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        torch.manual_seed(0)
        self.torch = torch
        self.name = hf_name(model)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = AutoProcessor.from_pretrained(self.name)
        self.model = AutoModelForImageTextToText.from_pretrained(self.name, dtype=torch.bfloat16).to(self.device).eval()

    def generate(self, prompt, images, max_tokens):
        import resource, sys
        from PIL import Image
        torch = self.torch
        if self.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        t = time.time()
        content = [{"type": "image", "image": Image.open(p).convert("RGB")} for p in images]
        messages = [{"role": "user", "content": content + [{"type": "text", "text": prompt}]}]
        inputs = self.processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                                    return_dict=True, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)
        new = out[0, inputs["input_ids"].shape[1]:]
        text = self.processor.decode(new, skip_special_tokens=True)
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        peak = torch.cuda.max_memory_allocated() if self.device == "cuda" else rss  # CPU: process peak
        return text, {"secs": round(time.time() - t, 1), "prompt_tokens": int(inputs["input_ids"].shape[1]),
                      "generation_tokens": int(new.shape[0]), "peak_gb": round(peak / 1e9, 2),
                      "finish_reason": "length" if new.shape[0] >= max_tokens else "stop"}


BACKENDS = {"mlx": MLX, "hf": HF}
