from src.utils.component_ids import get_component_id_resolver, normalize_component_ids


def test_component_id_resolver_maps_alias_to_canonical():
    resolver = get_component_id_resolver()
    assert resolver.resolve("core.payments") == "comp:payments"
    assert resolver.resolve("comp:payments") == "comp:payments"


def test_normalize_component_ids_deduplicates_and_maps():
    raw = ["core.payments", "comp:payments", "  "]
    normalized = normalize_component_ids(raw)
    assert normalized == ["comp:payments"]

