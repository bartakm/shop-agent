import json

from shop_agent.agent import run_inbox
from shop_agent.server import mcp


def call(id, name, args):
    return {"id": id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class FakeGroq:
    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []

    async def chat(self, messages, tools):
        self.requests.append({"messages": list(messages), "tools": tools})
        return {"finish_reason": "tool_calls", "message": {"content": "", "tool_calls": self.turns.pop(0)}}


def write_email(inbox, sender, body):
    inbox.mkdir(exist_ok=True)
    (inbox / "a.json").write_text(json.dumps({"from": sender, "subject": "test", "body": body}), encoding="utf-8")


async def test_groq_binds_sender_and_validates_draft(tmp_path):
    write_email(tmp_path / "in", "petr.svoboda@example.cz", "Kde je OBJ-1041?")
    groq = FakeGroq([
        [call("t1", "get_order", {"order_id": "OBJ-1041", "customer_email": "jana.novakova@example.cz"})],
        [call("t2", "submit_draft", {"category": "nonsense", "reply": "", "needs_human": False, "note_for_human": ""})],
        [call("t3", "submit_draft", {"category": "order_status", "reply": "...", "needs_human": True,
                                     "note_for_human": "neznámá objednávka"})],
    ])

    [result] = await run_inbox(tmp_path / "in", tmp_path / "out", client=groq, erp_target=mcp, provider="groq")

    get_order = next(t for t in groq.requests[0]["tools"] if t["function"]["name"] == "get_order")
    assert "customer_email" not in get_order["function"]["parameters"]["properties"]
    [action] = result.actions
    assert action["input"]["customer_email"] == "petr.svoboda@example.cz" and action["is_error"]
    assert groq.requests[2]["messages"][-1]["content"].startswith("Error: category")
    assert result.stop == "submitted" and result.category == "order_status"
