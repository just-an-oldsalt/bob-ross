# Publishing

Bob Ross ships a `server.json` manifest for the [official MCP Registry](https://registry.modelcontextprotocol.io).
Publishing is a two-step chore (agents can't do it for you — it needs your PyPI
and GitHub credentials).

## 1. Publish the package to PyPI

The registry entry points at a real installable package, so publish `bob-ross`
to PyPI first:

```bash
pip install build twine
python -m build
twine upload dist/*
```

> Note: `bob-ross` may be taken on PyPI. If so, rename the `[project].name` in
> `pyproject.toml` (e.g. `bob-ross-landscape`) and update `packages[].identifier`
> in `server.json` to match.

## 2. Publish to the MCP Registry

The `name` uses the GitHub namespace `io.github.just-an-oldsalt/*`, so ownership
is proven via GitHub login:

```bash
# Install the publisher CLI (see modelcontextprotocol/registry releases)
mcp-publisher login github
mcp-publisher publish     # reads ./server.json
```

Bump `version` in both `pyproject.toml` and `server.json` for each release, and
re-run both steps.

## CI

`.github/workflows/ci.yml` runs ruff (lint + format) and pytest on Python
3.11–3.13 for every push to `main` and every PR. Keep it green before publishing.
