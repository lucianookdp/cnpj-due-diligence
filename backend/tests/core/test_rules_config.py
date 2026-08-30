from app.core.rules_config import load_rules_config


def test_loads_the_real_rules_yaml():
    config = load_rules_config.__wrapped__()

    assert config.version >= 1
    rule_ids = {r.id for r in config.rules}
    assert "match_lista_restritiva" in rule_ids
    assert "empresa_recente" in rule_ids


def test_match_lista_restritiva_has_the_highest_weight():
    config = load_rules_config.__wrapped__()

    weights = {r.id: r.weight for r in config.rules}
    assert weights["match_lista_restritiva"] == max(weights.values())
