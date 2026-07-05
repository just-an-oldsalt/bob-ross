"""Entry point: `bob-ross` or `python -m bob_ross`. Runs over stdio by default."""

from __future__ import annotations

import sys

from .config import Settings
from .server import build_server


def main() -> None:
    try:
        settings = Settings()
    except Exception as exc:  # noqa: BLE001 — config errors should be friendly
        print(f"[bob-ross] configuration error: {exc}", file=sys.stderr)
        print("[bob-ross] copy .env.example to .env and fill it in.", file=sys.stderr)
        raise SystemExit(2) from exc

    if not settings.tls_verify:
        print("[bob-ross] WARNING: TLS verification is DISABLED. Dev use only.", file=sys.stderr)
    mode = "READ-ONLY" if not settings.writes_enabled else "WRITES ENABLED"
    print(f"[bob-ross] starting in {mode} mode (auth: {settings.auth_mode.value})", file=sys.stderr)

    build_server(settings).run()  # stdio transport


if __name__ == "__main__":
    main()
