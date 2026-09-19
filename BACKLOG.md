# Backlog

- **Probe in the live path.** The eval-time probe experiment is in the plan (step 3c). What stays here: a `ProbeJudge` behind the `Judge` interface for the live stream, which needs the watched model in-process (transformers, or vLLM with hooks) and so only applies to the same-box layout. Gated on the probe beating the text judge on the eval set.
- **Extra rubric categories, documented as recipes.** Sandbagging (deliberately underperforming while able) and hidden agenda (pursuing something nobody asked for: self-continuation, acquiring access, steering the user) were considered for the default and left out to keep it at three. Worth a docs page showing how to add them to a custom rubric, once the eval set can say whether the judge detects them.
- **Trained classifier judge.** Fine-tune a small encoder (ModernBERT class) on labeled traces for speed and cost once there is data. Same interface as `LLMJudge`.
- **CoT faithfulness caveat.** Text monitoring only sees what the model writes. Document this limit in the README rather than pretend otherwise; it is the argument for the probe work above.
