# Bob Ross 🎨

[![PyPI](https://img.shields.io/pypi/v/bob-ross-landscape.svg)](https://pypi.org/project/bob-ross-landscape/)
[![CI](https://github.com/just-an-oldsalt/bob-ross/actions/workflows/ci.yml/badge.svg)](https://github.com/just-an-oldsalt/bob-ross/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> *"We don't make mistakes, just happy little servers."*

An MCP server for managing a **Canonical Landscape** estate from an AI agent
(Claude Code / Desktop). Bob Ross wraps the Landscape API as calm, friendly MCP
tools — inventory, alerts, activities, patching, script execution, reboots — with
a **safety layer built right in**, so your agent can tend a whole fleet of happy
little servers without ever beating the devil out of the wrong one.

Everybody needs a friend. Even your Ubuntu estate.

---

## 🖌️ Why it's not just a dumb API wrapper

A blank canvas is a beautiful thing — and so is a fleet that's still standing.
Bob Ross paints carefully:

- **Blast-radius preview** — before you touch anything, `resolve_query` steps back
  from the easel and shows you *how many* machines a query matches (and a sample).
  Always know how big the canvas is.
- **Dry-run → confirm handshake** — every destructive tool returns a short-lived
  `confirm_token` on the first call. You have to call again *with* the token to
  actually do it. If the set of matched machines drifts in between, the token is
  refused. No happy little accident reboots 500 boxes.
- **Secure by default** — read-only mode is **on** out of the box (we all start
  with a clean canvas). Writes need *two* switches flipped on purpose. TLS is
  verified. Secrets never touch the logs.
- **Full audit log** — every stroke (dry runs, executes, denials) is appended to a
  redacted JSONL trail. You can always see what the brush did.
- **Activity-aware** — write actions in Landscape run later, asynchronously. Pass
  `wait=true` and Bob Ross watches the paint dry, then tells you succeeded /
  failed / still-going per machine — not just "queued."
- **Dual auth** — legacy HMAC query API *or* REST bearer token, auto-detected.

---

## 🎨 Get the paints out (install)

From PyPI — the whole studio in one command:

```bash
pip install bob-ross-landscape
```

That gives you the `bob-ross` command (the import package is `bob_ross`).

<details>
<summary>Or install from source (for hacking on it)</summary>

```bash
git clone https://github.com/just-an-oldsalt/bob-ross
cd bob-ross
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                    # run the safety / signing / config tests
```
</details>

---

## 🖼️ Set up your palette (configuration)

Everything is `BOBROSS_*` env vars (or a `.env` file — see `.env.example`):

| Var | Default | Meaning |
|---|---|---|
| `BOBROSS_LANDSCAPE_URL` | — | Landscape base URL (no trailing `/api/`) |
| `BOBROSS_ACCESS_KEY` / `BOBROSS_SECRET_KEY` | — | Legacy HMAC keys (mode A) |
| `BOBROSS_API_TOKEN` | — | REST bearer token (mode B) |
| `BOBROSS_READ_ONLY` | `true` | Blocks all writes — the safe blank canvas |
| `BOBROSS_ALLOW_WRITES` | `false` | The *second* switch needed to enable writes |
| `BOBROSS_TLS_VERIFY` | `true` | Verify TLS certs (set `false` only for dev self-signed) |

> To let Bob Ross pick up a brush, flip **both** `BOBROSS_READ_ONLY=false` **and**
> `BOBROSS_ALLOW_WRITES=true`. Even then, every destructive action still needs the
> dry-run → confirm handshake. Belt and suspenders. Happy and safe.

---

## 🪄 Add it to Claude Code

```bash
pip install bob-ross-landscape

claude mcp add bob-ross --scope user \
  --env BOBROSS_LANDSCAPE_URL=https://landscape.example.com \
  --env BOBROSS_ACCESS_KEY=YOUR_KEY \
  --env BOBROSS_SECRET_KEY=YOUR_SECRET \
  -- bob-ross
```

Prefer to keep secrets out of Claude's config? Put them in a `.env` file and run
from that directory instead:

```bash
claude mcp add bob-ross --scope user -- \
  bash -lc 'cd /path/to/your/bobross-env && exec bob-ross'
```

### Claude Desktop (stdio)

```json
{
  "mcpServers": {
    "bob-ross": {
      "command": "bob-ross",
      "env": {
        "BOBROSS_LANDSCAPE_URL": "https://landscape.example.com",
        "BOBROSS_ACCESS_KEY": "YOUR_KEY",
        "BOBROSS_SECRET_KEY": "YOUR_SECRET"
      }
    }
  }
}
```

Bob Ross always wakes up in read-only mode. Start there. Get comfortable. Then,
when you're ready, let's get a little crazy.

---

## 🌲 The brushes (tools)

**Read** (always safe — look all you like):
`ping` · `estate_health` · `list_computers` · `get_computer` · `resolve_query` ·
`pending_updates` · `list_alerts` · `list_activities` · `get_activity` ·
`wait_for_activity` · `list_scripts`

**Write** (gated — dry-run → confirm every time):
`execute_script` · `reboot_computers` · `apply_security_upgrades` ·
`upgrade_packages` · `install_packages` · `remove_packages` · `add_tags` ·
`remove_tags`

> Activity-creating write tools take `wait=true` to poll the resulting Landscape
> activity to a terminal status and hand back a `completion` summary
> (succeeded / failed / still-incomplete) — so your agent knows the real outcome,
> not just "queued."

**Resources:** `landscape://computers` · `landscape://alerts` ·
`landscape://health` · `landscape://computer/{computer_id}` (template)

**Prompts:** `patch_security_updates` · `triage_estate` ·
`reboot_reboot_required` · `patch_machine`

---

## 🏔️ A happy little workflow

You have unlimited power here. Move mountains — one confirmed step at a time:

```
you:  "what needs my attention across the fleet?"
       → estate_health  →  "kaylee-mc: 138 pending upgrades, 3 boxes need reboots"

you:  "what would patching kaylee-mc actually change?"
       → pending_updates title:kaylee-mc  →  the list, per package

you:  "apply the security upgrades there"
       → apply_security_upgrades  →  dry-run shows blast radius + a confirm_token
       → (you approve)            →  re-run with the token + wait=true
       → completion: succeeded ✅  no failed patches, just happy little servers
```

---

## 📦 Publishing & links

- **PyPI:** https://pypi.org/project/bob-ross-landscape/
- **Releases:** tag `vX.Y.Z`, `gh release create` → GitHub Actions publishes to PyPI
  via OIDC (no tokens). See [`PUBLISHING.md`](PUBLISHING.md).
- **MCP Registry manifest:** [`server.json`](server.json)

---

<div align="center">

*"Talent is a pursued interest. Anything you're willing to practice, you can do."*

Now go tend some happy little servers. 🎨

</div>
