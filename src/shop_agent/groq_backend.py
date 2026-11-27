"""Same agent loop as agent.handle_email, but against Groq's OpenAI-compatible API (free tier, open models).

Groq has no strict tool schemas, so submit_draft arguments are validated here and a bad call goes back
to the model as a tool error.
"""

import asyncio
import json
import os

import httpx

from .agent import BOUND_ARG, MAX_STEPS, SUBMIT_TOOL, Email, Result, tool_text

URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


def openai_tools(claude_tools: list[dict]) -> list[dict]:
    return [
        {"type": "function",
         "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in claude_tools
    ]


def validate_draft(args: dict) -> str | None:
    props = SUBMIT_TOOL["input_schema"]["properties"]
    missing = [k for k in SUBMIT_TOOL["input_schema"]["required"] if k not in args]
    if missing:
        return f"Missing fields: {', '.join(missing)}."
    if args["category"] not in props["category"]["enum"]:
        return f"category must be one of {props['category']['enum']}."
    if not isinstance(args["needs_human"], bool):
        return "needs_human must be true or false."
    if not isinstance(args["reply"], str) or not isinstance(args["note_for_human"], str):
        return "reply and note_for_human must be strings."
    return None


class GroqClient:
    def __init__(self, api_key: str | None = None, http: httpx.AsyncClient | None = None):
        self.api_key = api_key or os.environ["GROQ_API_KEY"]
        self.http = http or httpx.AsyncClient(timeout=120)

    async def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        for attempt in range(20):
            r = await self.http.post(
                URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": MODEL, "messages": messages, "tools": tools, "tool_choice": "auto",
                      "temperature": 0.2, "max_completion_tokens": 4000},
            )
            if r.status_code == 429:
                wait = float(r.headers.get("retry-after") or min(2 ** attempt, 30)) + 1
                print(f"   rate limit, waiting {wait:.0f} s", flush=True)
                await asyncio.sleep(min(wait, 90))
                continue
            if r.status_code == 400 and "tool_use_failed" in r.text:
                print("   model produced a malformed tool call, retrying", flush=True)
                continue
            break
        if r.is_error:
            raise RuntimeError(f"Groq {r.status_code}: {r.text[:300]}")
        return r.json()["choices"][0]


async def handle_email_groq(client: GroqClient, erp, email: Email, system: str, tools: list[dict],
                            bound: set[str]) -> Result:
    result = Result(email_id=email.id, sender=email.sender, subject=email.subject)
    tools = openai_tools(tools)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": (
            f"New customer email.\nSender address (verified by the mail server): {email.sender}\n"
            f"Subject: {email.subject}\n\n<email>\n{email.body}\n</email>"
        )},
    ]

    for _ in range(MAX_STEPS):
        choice = await client.chat(messages, tools)
        msg = choice["message"]
        calls = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls} if calls
                        else {"role": "assistant", "content": msg.get("content") or ""})

        if choice.get("finish_reason") == "length":
            result.stop = "max_tokens"
            result.note_for_human = "The model hit its output limit before finishing."
            return result
        if not calls:
            result.stop = "no_draft"
            result.note_for_human = "The agent stopped without submitting a draft."
            return result

        submitted = False
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": "Error: arguments are not valid JSON."})
                continue

            if name == SUBMIT_TOOL["name"]:
                problem = validate_draft(args)
                if problem:
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": f"Error: {problem}"})
                    continue
                result.category, result.reply = args["category"], args["reply"]
                result.needs_human, result.note_for_human = args["needs_human"], args["note_for_human"]
                submitted = True
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": "Draft saved."})
                continue

            if name in bound:
                args[BOUND_ARG] = email.sender
            out = await erp.call_tool(name, args)
            text = tool_text(out)
            result.actions.append({"tool": name, "input": args, "is_error": bool(out.is_error), "result": text})
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": ("Error: " + text) if out.is_error else text})

        if submitted:
            result.stop = "submitted"
            return result

    result.stop = "max_steps"
    result.note_for_human = f"The agent used {MAX_STEPS} steps without finishing."
    return result
