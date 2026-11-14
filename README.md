# shop-agent

An AI agent that answers customer emails for a small e-shop, working against the shop's ERP through MCP.

Zrnko is a fictional Czech coffee e-shop. Its ERP (products, stock, orders, returns) is a SQLite database
exposed as an **MCP server**. The **agent** reads incoming emails, looks things up and takes actions in the ERP
through that server using Claude, and writes a draft reply for each email, flagged when a person must decide.

```
inbox/*.json ──> agent (Claude, tool-use loop) ──MCP/stdio──> zrnko-erp server ──> SQLite
                        │                                        tools: search_products, get_product,
                        v                                               get_order, list_orders, create_return
                 outbox/*.md + results.json                      resource: shop://policy
```

The same MCP server also plugs straight into Claude Desktop or Claude Code, so staff can query the ERP in chat.

## Design decisions

- **Business rules live in the ERP, not in the prompt.** The 14-day return window, quantity limits and
  "only delivered orders" are enforced in `shop.py`. When the ERP refuses, the error text goes back to the
  model, which explains it to the customer. The model cannot talk its way past a rule.
- **The harness decides whose data the agent can see.** Order tools take `customer_email`, but that argument
  is removed from the schema Claude sees and filled with the verified sender address by the agent loop.
  A customer (or a prompt injection in the email) cannot read someone else's order.
- **Email text is untrusted.** The system prompt treats it as data; discounts, compensation and exceptions
  are never promised and go to a human.
- **Draft, not send.** Every email ends as a structured draft (`category`, `reply`, `needs_human`,
  `note_for_human`) via a strict `submit_draft` tool. Refusals, step limits and a missing draft fall back to
  "needs human".
- **Manual agent loop** instead of the SDK tool runner, because of the argument binding above and to log
  every ERP call per email.
- Model `claude-opus-5-5` at medium effort, with server-side refusal fallback enabled
  (`fallbacks: "default"`).

## Sample inbox

| Email | What it tests |
|---|---|
| `01-stock` | stock lookup, sold-out item with restock date, product recommendation |
| `02-where-is-order` | order status with carrier and tracking number |
| `03-return` | creates a return in the ERP (`create_return`) |
| `04-late-return` | return after 14 days: ERP refuses, angry tone, goes to a human |
| `05-other-persons-order` | asks for someone else's order: lookup is bound to the sender, nothing leaks |
| `06-injection` | prompt injection asking for a 50 % discount |
| `07-spam` | SEO spam, no reply |

## Run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
export ANTHROPIC_API_KEY=...        # PowerShell: $env:ANTHROPIC_API_KEY="..."
export SHOP_TODAY=2026-11-14        # optional: fix "today" so the sample data's return windows line up
uv run shop-agent inbox --out outbox
```

The database is created and seeded in `data/shop.db` on first run. Delete it to reset.

### Score the run

```bash
uv run shop-eval outbox/results.json
```

`evals/cases.json` states what a correct handling of each sample email looks like: category, whether a human must
look at it, which ERP calls must succeed or must not succeed, and text the reply must contain or must not contain
(the tracking number for the owner; no tracking number, carrier or items for a stranger; no "50 %" for the injection).
The scorer prints every failed check and exits non-zero unless all emails pass, so it can gate a prompt or model change.
Delete `data/shop.db` before each run so returns from earlier runs don't change the result.

### Use the ERP from Claude Desktop / Claude Code

```json
{
  "mcpServers": {
    "zrnko-erp": {
      "command": "uv",
      "args": ["--directory", "/path/to/shop-agent", "run", "shop-erp"],
      "env": { "SHOP_TODAY": "2026-11-14" }
    }
  }
}
```

## Tests

```bash
uv run pytest
```

Covers the ERP rules, the MCP server (in memory) and the agent loop with a scripted fake model: sender binding,
a return created through MCP, and the fallback to a human when no draft is submitted. The eval scorer is tested too:
a failed ERP call doesn't count as done, and a leaked tracking number or a promised discount fails the case.
The tests need no API key.

## Layout

```
src/shop_agent/
  db.py       schema and seed data
  shop.py     ERP logic and business rules
  server.py   MCP server (tools + policy resource)
  agent.py    agent loop, MCP-to-Claude tool bridge, drafts
  evals.py    scores results.json against evals/cases.json
inbox/        sample customer emails
evals/        expected outcome for each sample email
tests/
```
