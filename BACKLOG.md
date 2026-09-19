# Backlog

- **Hidden-state probes.** Hook the residual stream during local generation (transformers / vLLM) and train a linear probe or small MLP on activations. Catches what the model does not verbalize; harder to game than text. Per-model, needs local inference, research before product. Plugs in behind the `Judge` interface.
- **Trained classifier judge.** Fine-tune a small encoder (ModernBERT class) on labeled traces for speed and cost once there is data. Same interface as `LLMJudge`.
- **Proxy server** (v1.1). Local OpenAI-compatible endpoint that forwards to the real inference server and watches the stream. Zero code change for the user, any language.
- **CoT faithfulness caveat.** Text monitoring only sees what the model writes. Document this limit in the README rather than pretend otherwise; it is the argument for the probe work above.
