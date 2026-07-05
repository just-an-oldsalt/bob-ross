"""Guard the registered MCP surface so tools/resources/prompts can't silently vanish."""

from bob_ross.config import Settings
from bob_ross.server import build_server


def _server():
    return build_server(Settings(landscape_url="https://ls.example.com", api_token="t"))


async def test_expected_tools_registered():
    names = {t.name for t in await _server().list_tools()}
    for expected in (
        "ping", "estate_health", "pending_updates", "resolve_query",
        "reboot_computers", "execute_script", "apply_security_upgrades",
        "wait_for_activity", "add_tags", "remove_tags",
    ):
        assert expected in names, f"missing tool {expected}"


async def test_resources_and_templates_registered():
    m = _server()
    res = {str(r.uri) for r in await m.list_resources()}
    assert {"landscape://computers", "landscape://alerts", "landscape://health"} <= res
    templates = {t.uri_template for t in await m.list_resource_templates()}
    assert "landscape://computer/{computer_id}" in templates


async def test_prompts_registered():
    prompts = {p.name for p in await _server().list_prompts()}
    assert {
        "patch_security_updates", "triage_estate", "reboot_reboot_required", "patch_machine"
    } <= prompts
