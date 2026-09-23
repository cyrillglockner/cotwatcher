"""Pooled residual-stream activations for reasoning chunks.

Runs the watched model *forward* over text we already have (no generation),
hooks the hidden states, and mean-pools each chunk's tokens at a few layers.
The chunk is placed where the model's own thinking would go, after the task
and inside the <think> block, so the activations are of the model "reading"
this reasoning as its own.

    from evals.probe.activations import Extractor
    ex = Extractor("deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B")
    feats = ex.pooled(task, context, chunk)      # {layer_idx: np.ndarray[hidden]}
"""

from __future__ import annotations

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# A probe lives in one model's residual stream, so the probed model must be the
# *watched* model. `qwen3.5-9b` is the current watched model (it produced the
# pressure episodes); the R1 entries are from the earlier feasibility work and
# their probes do not transfer.
MODELS = {
    "qwen3.5-9b": "Qwen/Qwen3.5-9B",
    "1.5b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
    "7b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
}


def pick_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class Extractor:
    def __init__(self, model_id: str, device: str | None = None, layers: list[int] | None = None):
        self.device = device or pick_device()
        self.model_id = model_id
        self.tok = AutoTokenizer.from_pretrained(model_id)
        self.dtype = torch.float16 if self.device != "cpu" else torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(model_id, dtype=self.dtype).to(self.device).eval()
        self.model.config.use_cache = False   # no KV cache: one forward pass, no generation
        n = self.model.config.num_hidden_layers
        # hidden_states[0] is the embedding output, so layer i's output is index i+1
        self.layers = layers or sorted({n // 4, n // 2, (3 * n) // 4, n})
        self.n_layers = n

    def identity(self) -> str:
        """Everything about this extractor that changes the numbers it returns."""
        rev = getattr(self.model.config, "_commit_hash", None) or "local"
        return "|".join([self.model_id, str(rev), str(self.dtype), self.device,
                         ",".join(map(str, self.layers)), f"pool=mean", f"tok={self.tok.name_or_path}"])

    def _prompt(self, task: str, context: str) -> str:
        msgs = [{"role": "user", "content": task}] if task else []
        prefix = self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True) if msgs else ""
        if "<think>" not in prefix:
            prefix += "<think>\n"
        return prefix + (context + "\n" if context else "")

    @torch.no_grad()
    def pooled(self, task: str, context: str, chunk: str) -> dict[int, np.ndarray]:
        prefix = self._prompt(task, context)
        p_ids = self.tok(prefix, return_tensors="pt", add_special_tokens=False).input_ids
        c_ids = self.tok(chunk, return_tensors="pt", add_special_tokens=False).input_ids
        ids = torch.cat([p_ids, c_ids], dim=1).to(self.device)
        out = self.model(ids, output_hidden_states=True, use_cache=False)
        start = p_ids.shape[1]
        feats = {}
        for L in self.layers:
            h = out.hidden_states[L][0, start:, :]  # chunk tokens only
            feats[L] = h.float().mean(dim=0).cpu().numpy()
        del out                                    # hidden states for every layer are large
        if self.device == "mps":
            torch.mps.empty_cache()
        return feats
