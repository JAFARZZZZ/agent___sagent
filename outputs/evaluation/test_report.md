# Validation report

Executed on 2026-10-22 with Python 3.14.6.

- `python -m unittest discover -s tests -v`: 21 tests passed, 6.459 seconds (warm search index).
- Real-catalog integration: counts, category coverage, two-product comparison, three category journeys, persistent requests, authenticated seller responses, unavailable follow-up, same-product alternatives, budget and input validation.
- `python -m scripts.verify_web_catalog`: 225,903 products and FTS rows; 6,476 shops; 331,506 offers; 3,428 categories; zero foreign-key violations.
- Five sample lexical queries: 86.12–226.43 ms locally. This is not a load benchmark.
- `git diff --cached --check`: passed.

Initial test assumed no one-toman offers; actual source records contradicted that assumption. Replaced it with a hard budget preservation assertion. Source prices were not changed.

Not executed: browser visual/accessibility QA, Docker image build, hosted deployment, live LLM validation. TestClient emits an upstream httpx deprecation warning. No lint/type-check configuration existed.
