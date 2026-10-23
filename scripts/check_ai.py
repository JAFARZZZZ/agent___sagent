"""Quick live check of the configured AI provider (chat + tools + embeddings). Never prints the key.

  python -m scripts.check_ai
"""
import os
import time

from backend import config  # noqa: F401  (loads .env)
from openai import OpenAI


def main():
    base, model = os.getenv('OPENAI_BASE_URL') or 'https://api.openai.com/v1', os.getenv('OPENAI_MODEL')
    print(f'base_url={base}  model={model}  key={"set" if os.getenv("OPENAI_API_KEY") else "MISSING"}')
    client = OpenAI(base_url=os.getenv('OPENAI_BASE_URL') or None, timeout=30, max_retries=0)
    tool = {'type': 'function', 'function': {'name': 'search_products', 'description': 'search', 'parameters': {
        'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']}}}
    t = time.time()
    try:
        r = client.chat.completions.create(model=model, messages=[{'role': 'user', 'content': 'دنبال گوشی سامسونگ هستم، جستجو کن'}], tools=[tool])
        calls = r.choices[0].message.tool_calls or []
        print(f'chat+tools: OK in {time.time()-t:.1f}s, tool call: {calls[0].function.name + " " + calls[0].function.arguments if calls else "none"}')
    except Exception as exc:
        print(f'chat+tools: FAILED {type(exc).__name__}: {str(exc)[:200]}')
    emb_model = os.getenv('EMBEDDING_MODEL') or 'text-embedding-3-small'
    emb = OpenAI(api_key=os.getenv('EMBEDDING_API_KEY') or os.getenv('OPENAI_API_KEY'),
                 base_url=os.getenv('EMBEDDING_BASE_URL') or os.getenv('OPENAI_BASE_URL') or None, timeout=30, max_retries=0)
    t = time.time()
    try:
        d = emb.embeddings.create(model=emb_model, input=['گوشی سامسونگ', 'هدفون بی سیم'], dimensions=int(os.getenv('EMBEDDING_DIMENSIONS') or 512))
        print(f'embeddings ({emb_model}): OK in {time.time()-t:.1f}s, dims={len(d.data[0].embedding)}')
    except Exception as exc:
        print(f'embeddings ({emb_model}): FAILED {type(exc).__name__}: {str(exc)[:200]}')


if __name__ == '__main__':
    main()
