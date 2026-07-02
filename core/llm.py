"""
llm.py — provider-abstracted LLM transport.
===========================================
One place that knows how to talk to either OpenAI or Anthropic. The rest of the
codebase (claude_client.py chat loop, intelligence.py prose) calls these helpers
so switching providers is a config flag (LLM_PROVIDER) — nothing else changes.

IMPORTANT: this module changes only *how* requests are sent. The tool
definitions, the system prompts, and the deterministic tool-calling behaviour
live in their original files and are passed in unchanged. The LLM never computes
numbers; it only selects tools and phrases answers.

Uses the Python standard library only (urllib) — no SDKs.
"""

import json
import urllib.request
import urllib.error

import config


OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def provider() -> str:
    return "anthropic" if config.LLM_PROVIDER == "anthropic" else "openai"


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{provider()} API error {e.code}: "
                           f"{e.read().decode(errors='replace')}")


def _openai_headers():
    return {"content-type": "application/json",
            "authorization": f"Bearer {config.OPENAI_API_KEY}"}


def _anthropic_headers():
    return {"content-type": "application/json",
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"}


def _extract_json(text):
    """Best-effort parse of a JSON object from model text (Anthropic has no
    response_format=json_object, so we defensively extract the first object)."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _to_anthropic_tools(openai_tools):
    """Convert OpenAI function-tool schema -> Anthropic tool schema (same
    names, descriptions, and JSON-schema parameters; nothing about the tool
    contract changes)."""
    out = []
    for t in openai_tools:
        f = t["function"]
        out.append({
            "name": f["name"],
            "description": f.get("description", ""),
            "input_schema": f.get("parameters") or {"type": "object", "properties": {}},
        })
    return out


# ===========================================================================
# 1. JSON completion (used by intelligence.py for the Signals prose)
# ===========================================================================
def complete_json(system, user_content, max_tokens):
    """Return a parsed JSON object from the model, or None on failure."""
    if provider() == "anthropic":
        body = {
            "model": config.ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user",
                          "content": user_content + "\n\nReturn ONLY valid JSON, no prose."}],
        }
        try:
            data = _post(ANTHROPIC_URL, body, _anthropic_headers(), 120)
            text = "".join(b.get("text", "") for b in data.get("content", [])
                           if b.get("type") == "text")
            return _extract_json(text)
        except (RuntimeError, urllib.error.URLError, KeyError, TimeoutError) as e:
            print(f"  ! intelligence model call failed ({e}); deterministic fallback.")
            return None
    else:
        body = {
            "model": config.OPENAI_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user_content}],
            "response_format": {"type": "json_object"},
        }
        try:
            data = _post(OPENAI_URL, body, _openai_headers(), 120)
            content = data["choices"][0]["message"].get("content") or "{}"
            return json.loads(content)
        except (RuntimeError, urllib.error.URLError, KeyError,
                json.JSONDecodeError, TimeoutError) as e:
            print(f"  ! intelligence model call failed ({e}); deterministic fallback.")
            return None


# ===========================================================================
# 2. Tool-calling conversation (used by claude_client.py for the Ask chat)
#    tool_runner(name, args) -> dict result. If a result has a "chart" key it
#    is collected for the UI. Returns {answer, trace, charts}.
# ===========================================================================
def run_tool_conversation(system, history, user_message, tools, tool_runner, max_rounds):
    if provider() == "anthropic":
        return _anthropic_loop(system, history, user_message, tools, tool_runner, max_rounds)
    return _openai_loop(system, history, user_message, tools, tool_runner, max_rounds)


def _collect_chart(result, charts):
    if isinstance(result, dict) and "chart" in result:
        charts.append(result["chart"])


def _openai_loop(system, history, user_message, tools, tool_runner, max_rounds):
    messages = [{"role": "system", "content": system}]
    messages += list(history or [])
    messages.append({"role": "user", "content": user_message})
    trace, charts = [], []
    for _ in range(max_rounds):
        body = {"model": config.OPENAI_MODEL, "max_tokens": config.MAX_TOKENS,
                "messages": messages, "tools": tools}
        data = _post(OPENAI_URL, body, _openai_headers(), 90)
        msg = data["choices"][0]["message"]
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            return {"answer": (msg.get("content") or "").strip(), "trace": trace, "charts": charts}
        messages.append(msg)
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            trace.append({"tool": name, "arguments": args})
            result = tool_runner(name, args)
            _collect_chart(result, charts)
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": json.dumps(result)})
    return {"answer": "I couldn't complete that within the step limit.",
            "trace": trace, "charts": charts}


def _anthropic_loop(system, history, user_message, tools, tool_runner, max_rounds):
    a_tools = _to_anthropic_tools(tools)
    # History arrives as OpenAI-style {role, content} text turns — directly
    # compatible with Anthropic user/assistant string messages.
    messages = [m for m in (history or []) if m.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": user_message})
    trace, charts = [], []
    for _ in range(max_rounds):
        body = {"model": config.ANTHROPIC_MODEL, "max_tokens": config.MAX_TOKENS,
                "system": system, "messages": messages, "tools": a_tools}
        data = _post(ANTHROPIC_URL, body, _anthropic_headers(), 90)
        content = data.get("content", [])
        text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        if not tool_uses or data.get("stop_reason") != "tool_use":
            return {"answer": text.strip(), "trace": trace, "charts": charts}
        messages.append({"role": "assistant", "content": content})
        tool_results = []
        for tu in tool_uses:
            name, args = tu.get("name"), tu.get("input") or {}
            trace.append({"tool": name, "arguments": args})
            result = tool_runner(name, args)
            _collect_chart(result, charts)
            tool_results.append({"type": "tool_result", "tool_use_id": tu.get("id"),
                                 "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})
    return {"answer": "I couldn't complete that within the step limit.",
            "trace": trace, "charts": charts}
