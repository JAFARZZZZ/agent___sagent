# Search behavior

Shared FTS5 index includes every product title, model, brand, category and raw specifications. Persian normalization preserves model digits. Prefix AND retrieval supports concise mixed-language terms; it does not guarantee exact variant identity. The agent can reformulate text through multiple calls, while saved budget/category constraints remain backend filters. Seller retrieval preserves budget and numeric radius constraints. Unknown inventory is never inferred from an offer.

Search ranking remains stable product ID order; semantic, relevance reranking and joint product–store scores are not implemented. All categories remain discoverable through name lookup. Analytical fields and joins are allowlisted in `backend/agent/query.py`; parameters never become SQL identifiers. Query results are capped and have a progress-handler deadline.
