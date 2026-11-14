from mcp import Client

from shop_agent.server import mcp


async def test_tools_listed():
    async with Client(mcp) as c:
        names = {t.name for t in (await c.list_tools()).tools}
    assert names == {"search_products", "get_product", "get_order", "list_orders", "create_return"}


async def test_business_rule_error_reaches_the_model():
    async with Client(mcp) as c:
        r = await c.call_tool(
            "create_return",
            {"order_id": "OBJ-0987", "customer_email": "eva.dvorakova@example.cz", "sku": "ZR-KET-600",
             "quantity": 1, "reason": "x"},
        )
    assert r.is_error
    assert "Lhůta 14 dnů" in r.content[0].text


async def test_policy_resource():
    async with Client(mcp) as c:
        policy = (await c.read_resource("shop://policy")).contents[0].text
    assert "14 dnů od doručení" in policy
