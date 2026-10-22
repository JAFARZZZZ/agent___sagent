import json
import unittest
from unittest.mock import patch
from scripts.shopping_agent import ChatClient, ShoppingAgent


def tool_call(arguments, name="search_phones"):
    return {"role":"assistant", "content":None, "tool_calls":[{"id":"call1", "type":"function", "function":{"name":name,"arguments":json.dumps(arguments)}}]}


class FakeClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.seen = []

    def complete(self, messages):
        self.seen.append(list(messages))
        return next(self.replies)


class AgentTests(unittest.TestCase):
    def test_real_database_tool_roundtrip(self):
        args = dict(query="A55 256GB",max_price_toman=200000000,lat=35.7,lon=51.4,radius_km=10)
        client = FakeClient([tool_call(args), {"role":"assistant","content":"Recorded results returned."}])
        agent = ShoppingAgent(client)
        self.assertEqual(agent.turn("Find a phone"), "Recorded results returned.")
        data = json.loads(client.seen[1][-1]["content"])
        self.assertGreater(data["total_matches"], 0)
        self.assertTrue(all(r["inventory_status"] == "unknown" for r in data["results"]))
        self.assertEqual(len(agent.trace), 1)

    def test_invalid_arguments_and_unknown_tool(self):
        agent = ShoppingAgent(None)
        with patch("scripts.shopping_agent.search") as search:
            self.assertIn("error", agent.execute_tool(tool_call({})["tool_calls"][0]))
            self.assertIn("error", agent.execute_tool(tool_call({},"delete_data")["tool_calls"][0]))
            search.assert_not_called()

    def test_clarification_and_history(self):
        client = FakeClient([{"role":"assistant","content":"What is your budget?"}])
        agent = ShoppingAgent(client)
        agent.turn("Help me choose")
        self.assertEqual(len(agent.messages), 3)
        self.assertEqual(agent.trace, [])

    def test_loop_limit_does_not_commit_partial_history(self):
        agent = ShoppingAgent(FakeClient([tool_call({}),tool_call({})]),max_rounds=2)
        with self.assertRaises(RuntimeError):
            agent.turn("Find phone")
        self.assertEqual(len(agent.messages), 1)

    def test_configuration_rejects_missing_key_or_plain_http(self):
        with self.assertRaises(ValueError):
            ChatClient("https://example.com/v1", "model", "")
        with self.assertRaises(ValueError):
            ChatClient("http://example.com/v1", "model", "key")
