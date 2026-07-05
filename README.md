# Bob Ross 🎨

> *"We don't make mistakes, just happy little servers."*

An MCP server for managing a **Canonical Landscape** estate from an AI agent
(Claude Desktop / Claude Code). Bob Ross wraps the Landscape API as MCP tools —
inventory, alerts, activities, patching, script execution — with a **safety layer
built in** so an LLM can't accidentally reboot your whole fleet.

Jira: **BR**

## Why it's not just a dumb API wrapper

- **Blast-radius preview** — `resolve_query` shows *how many* machines a query
  matches (and a sample) before you act.
- **Dry-run → confirm handshake** — every destructive tool returns a short-lived
  `confirm_token` on the first call; you must call again *with* the token to
  execute. If the matched machine set drifts in between, the token is rejected.
- **Secure by default** — read-only mode is **on** out of the box. Writes need
  *two* explicit switches flipped. TLS is verified. Secrets never hit logs.
- **Full audit log** — every action (dry runs, executes, denials) is appended to
  a redacted JSONL audit trail.
- **Dual auth** — REST bearer token *or* legacy HMAC query API, auto-detected.

## Status

MVP scaffold. Read tools + gated write tools are implemented against both API
backends. Exact REST endpoint paths are set as constants in `client.py` and get
finalized once pointed at a live instance — run the `ping` tool to validate.

## Setup

```bash
python3.14 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # then fill in URL + credentials
pytest                    # run the safety/signing/config tests
```

## Configuration

All via `BOBROSS_*` env vars (or `.env`). See `.env.example`. Key ones:

| Var | Default | Meaning |
|---|---|---|
| `BOBROSS_LANDSCAPE_URL` | — | Landscape base URL |
| `BOBROSS_API_TOKEN` | — | REST bearer token (mode A) |
| `BOBROSS_ACCESS_KEY` / `BOBROSS_SECRET_KEY` | — | Legacy HMAC keys (mode B) |
| `BOBROSS_READ_ONLY` | `true` | Blocks all writes |
| `BOBROSS_ALLOW_WRITES` | `false` | Second switch required for writes |
| `BOBROSS_TLS_VERIFY` | `true` | Verify TLS certs |

## Run

```bash
bob-ross            # stdio transport (Claude Desktop / Code)
# or
python -m bob_ross
```

### Claude Desktop / Code (stdio)

```json
{
  "mcpServers": {
    "bob-ross": {
      "command": "/path/to/bob-ross/.venv/bin/bob-ross",
      "env": { "BOBROSS_LANDSCAPE_URL": "https://landscape.example.com",
               "BOBROSS_API_TOKEN": "..." }
    }
  }
}
```

## Tools

**Read:** `ping`, `list_computers`, `get_computer`, `resolve_query`,
`list_alerts`, `list_activities`, `get_activity`, `list_scripts`
**Write (gated):** `execute_script`, `reboot_computers`,
`apply_security_upgrades`, `add_tags`

**Resources:** `landscape://computers`, `landscape://alerts`
**Prompts:** `patch_security_updates`
