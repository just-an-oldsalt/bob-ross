# Publishing

Bob Ross ships a `server.json` manifest for the [official MCP Registry](https://registry.modelcontextprotocol.io).
Publishing is a two-step chore (agents can't do it for you — it needs your PyPI
and GitHub credentials).

## 1. Publish the package to PyPI (Trusted Publishing / OIDC)

No API tokens. `.github/workflows/publish.yml` publishes to PyPI automatically
when you create a GitHub Release, authenticating via OIDC.

One-time setup on PyPI — add a **pending publisher**
(PyPI → your account → Publishing → Add):

| Field | Value |
| --- | --- |
| PyPI Project Name | `bob-ross` |
| Owner | `just-an-oldsalt` |
| Repository name | `bob-ross` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

Then, in the GitHub repo, create an Environment named `pypi`
(Settings → Environments) — optionally gate it with required reviewers.

To release:

```bash
# bump version in pyproject.toml AND server.json, commit, then:
git tag v0.1.0 && git push origin v0.1.0
gh release create v0.1.0 --generate-notes    # <- fires publish.yml
```

> Note: `bob-ross` may be taken on PyPI. If so, rename `[project].name` in
> `pyproject.toml` (e.g. `bob-ross-landscape`), update `packages[].identifier`
> in `server.json`, and use that name in the PyPI publisher form above.

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
