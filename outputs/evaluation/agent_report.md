# Agent validation — 2026-10-22

Executed `.venv/Scripts/python -m unittest discover -s tests -v`: **25 passed in 18.876 seconds**.

New tests cover multi-round Responses protocol with real catalog retrieval, persisted history, budget preservation across preference updates, missing-configuration fallback, denied seller mutation, safe analytical aggregation and SQL identifier/value injection rejection. Existing real-data tests cover three dynamically selected categories and persisted simulated seller response journeys.

The model client is a deterministic test double. These results do not measure Persian intent accuracy, hallucination rate, ranking quality, live provider compatibility or live model latency. No OpenAI credentials/model are configured in this project's environment. Live evaluation remains pending. Browser rendering and Docker execution were not tested.

No dataset files or user `.env` values were changed. Source catalog coverage remains validated by the existing integration suite.
