"""Contracts for the gradual DDD ownership registry."""

from app.domains import DOMAIN_REGISTRY


def test_core_handover_domains_are_registered() -> None:
    assert {
        "crm",
        "approval",
        "finance",
        "growth_vmd",
        "agent_platform",
        "enterprise_core",
        "integrations",
        "admin_trust",
    } <= DOMAIN_REGISTRY.keys()


def test_domain_codes_match_keys_and_have_owners() -> None:
    for key, descriptor in DOMAIN_REGISTRY.items():
        assert descriptor.code == key
        assert descriptor.owner != "unassigned"


def test_router_and_service_ownership_does_not_overlap() -> None:
    for attribute in ("routers", "services"):
        owners: dict[str, str] = {}
        for domain, descriptor in DOMAIN_REGISTRY.items():
            for item in getattr(descriptor, attribute):
                assert item not in owners, (
                    f"{attribute[:-1]} {item!r} is owned by both "
                    f"{owners[item]!r} and {domain!r}"
                )
                owners[item] = domain
