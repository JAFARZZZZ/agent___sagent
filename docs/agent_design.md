# Agent architecture and contracts

`POST /api/sessions/{id}/chat` takes `{ "message": "..." }` and returns validated message, response type, components, warnings and token/timing metrics. Session IDs are bearer capabilities. Keep the service local or behind access control.

The Responses loop follows the official function-calling protocol: https://developers.openai.com/api/docs/guides/function-calling . It sends typed function schemas, appends complete output items, executes validated calls, then appends function_call_output items using call_id. No provider response storage is requested. Sequential tool execution is bounded to eight rounds maximum and six calls per round. The overall model timeout defaults to 45 seconds. Existing tool operations can add local execution time.

Tool registry: `backend/agent/tools.py`; each entry contains its purpose and Pydantic input model. Empty tools reject extra arguments. Identity tools require IDs, comparison accepts two to four IDs, search strings are capped at 300 characters, analytical queries at 50 rows. Errors are returned without raw provider messages or credentials. Seller mutation is unavailable to the model. Preference changes clear incompatible selections.

Available domains: schema/coverage/categories, product search/details/comparison, offer retrieval, store details/comparison, preferences/session, confirmation status, alternatives, shopping plans, analytical catalog query. Geographic and budget constraints are inherited by seller tools. Missing coordinates fail radius filtering rather than being invented.

The frontend renders agent prose as textContent and product results using escaped backend records. Other structured results are expandable JSON pending richer comparison/store components. Manual search and confirmation stay available without OpenAI.

Deployment uses the existing SQLite database and static frontend. See IMPLEMENTATION_STATUS.md for gaps; PostgreSQL and Next.js were not silently claimed as implemented.
