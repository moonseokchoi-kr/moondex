# Live Evaluations

Live evaluations are opt-in and are not collected by the offline test suite.
Use the explicit boundary command:

```bash
python3 evals/run-live-eval.py --confirm-live
```

It intentionally does not run as part of `pytest tests/` or the offline
benchmark command. Configure a live evaluator adapter before using it against
an LLM or another external service.
