import json
from types import SimpleNamespace

from shop_agent.agent import run_inbox
from shop_agent.server import mcp


def tool_use(id, name, input):
    return SimpleNamespace(type="tool_use", id=id, name=name, input=input)


class FakeClaude:
    """Plays back scripted responses and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        content = self.responses.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return SimpleNamespace(stop_reason=stop, content=content)


def write_email(inbox, name, sender, body):
    inbox.mkdir(exist_ok=True)
    (inbox / f"{name}.json").write_text(
        json.dumps({"from": sender, "subject": "test", "body": body}), encoding="utf-8"
    )


async def test_order_lookup_is_bound_to_sender(tmp_path):
    write_email(tmp_path / "in", "a", "petr.svoboda@example.cz", "Kde je OBJ-1041?")
    claude = FakeClaude([
        [tool_use("t1", "get_order", {"order_id": "OBJ-1041", "customer_email": "jana.novakova@example.cz"})],
        [tool_use("t2", "submit_draft", {"category": "order_status", "reply": "...", "needs_human": False,
                                         "note_for_human": ""})],
    ])

    [result] = await run_inbox(tmp_path / "in", tmp_path / "out", client=claude, erp_target=mcp)

    get_order = next(t for t in claude.requests[0]["tools"] if t["name"] == "get_order")
    assert "customer_email" not in get_order["input_schema"]["properties"]
    [action] = result.actions
    assert action["input"]["customer_email"] == "petr.svoboda@example.cz"
    assert action["is_error"]
    second_turn = claude.requests[1]["messages"][-1]["content"][0]
    assert second_turn["is_error"] and "nebyla nalezena" in second_turn["content"]
    assert result.stop == "submitted"
    assert (tmp_path / "out" / "a.md").exists()


async def test_return_is_created_through_mcp(tmp_path):
    write_email(tmp_path / "in", "a", "jana.novakova@example.cz", "Vracím dripper z OBJ-1041.")
    claude = FakeClaude([
        [tool_use("t1", "create_return", {"order_id": "OBJ-1041", "sku": "ZR-V60-02", "quantity": 1,
                                          "reason": "dárek dvakrát"})],
        [tool_use("t2", "submit_draft", {"category": "return_request", "reply": "VR-0001", "needs_human": False,
                                         "note_for_human": ""})],
    ])

    [result] = await run_inbox(tmp_path / "in", tmp_path / "out", client=claude, erp_target=mcp)

    assert not result.actions[0]["is_error"]
    assert '"return_id": "VR-0001"' in result.actions[0]["result"]
    assert result.needs_human is False


async def test_agent_without_draft_goes_to_human(tmp_path):
    write_email(tmp_path / "in", "a", "x@example.cz", "Ahoj")
    claude = FakeClaude([[SimpleNamespace(type="text", text="Hello")]])

    [result] = await run_inbox(tmp_path / "in", tmp_path / "out", client=claude, erp_target=mcp)

    assert result.needs_human and result.stop == "no_draft"


def test_guard_sends_promised_discount_to_human():
    from shop_agent.agent import Result, guard

    r = guard(Result("a", "x@example.cz", "s", reply="Potvrzujeme slevu 50 %.", needs_human=False, stop="submitted"))
    assert r.needs_human and "discount" in r.note_for_human
    ok = guard(Result("b", "x@example.cz", "s", reply="Objednávka je na cestě.", needs_human=False, stop="submitted"))
    assert not ok.needs_human
