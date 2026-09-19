# Backlog

- **Hidden-state probes.** Hook the residual stream during local generation (transformers / vLLM) and train a linear probe or small MLP on activations. Catches what the model does not verbalize; harder to game than text. Per-model, needs local inference, research before product. Plugs in behind the `Judge` interface.
- **Extra rubric categories, documented as recipes.** Sandbagging (deliberately underperforming while able) and hidden agenda (pursuing something nobody asked for: self-continuation, acquiring access, steering the user) were considered for the default and left out to keep it at three. Worth a docs page showing how to add them to a custom rubric, once the eval set can say whether the judge detects them.
- **Trained classifier judge.** Fine-tune a small encoder (ModernBERT class) on labeled traces for speed and cost once there is data. Same interface as `LLMJudge`.
- **CoT faithfulness caveat.** Text monitoring only sees what the model writes. Document this limit in the README rather than pretend otherwise; it is the argument for the probe work above.
