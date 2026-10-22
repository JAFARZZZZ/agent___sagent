# Agent implementation status

Implemented: official OpenAI Python SDK Responses function-calling loop, configurable model, backend-only credentials, bounded rounds/tokens/time, duplicate call detection, persisted conversation and trace, validated domain tools, category-independent retrieval, comparisons, geographic seller filtering, simulated confirmation status and plan, structured UI components derived only from backend tool results. Project `.env` now loads automatically without overriding process environment.

Analytical DSL supports allowlisted projections, approved product–offer–shop joins, AND/OR filters, numeric/text/date-string comparisons, count/min/max/avg, grouping, sorting, offset pagination, and a three-second SQLite query deadline. No raw SQL, arbitrary writes, secret access or seller-response mutation is exposed.

Existing confirmation button remains the explicit user action that creates requests. The agent can inspect the resulting status and alternatives. Price responses exceeding the saved budget now trigger ALTERNATIVE_REQUIRED.

Not complete: PostgreSQL/DATABASE_URL migration, Next.js migration, installment filtering, generic geo aggregations, distinct/having DSL, joint ranking, similar-product recommendation, structured required-attribute enforcement, geocoding, embedded map, live response polling, authenticated customer accounts, distributed session concurrency control, quantitative relevance evaluation. AGENT_DEBUG configuration and monetary cost estimation are not implemented; token usage is recorded instead.

Important limits: hard budget/category/location values already stored are applied by domain retrieval. Natural-language extraction depends on model behavior; arbitrary attribute constraints are not enforced. Analytical queries are exploration tools and do not automatically inherit session filters. Model prose is prompted to be grounded, not formally claim-verified. Product cards come from retrieved data. Conversation stores the last six exchanges, not all historic tool evidence. Unsupported requests should prompt clarification.

Live OpenAI verification is blocked: project `.env` has no OPENAI_API_KEY or OPENAI_MODEL. Automated tests use a deterministic Responses client double with real catalog operations; this is not live model validation. No Git remote is configured. Docker and browser visual QA remain unverified.
