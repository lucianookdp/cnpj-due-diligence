from datetime import UTC, datetime, timedelta

from app.core.rules_config import RuleConfig, RulesConfig
from app.models import Company, Partnership, Person, RestrictiveListEntry
from app.services import risk_scoring
from app.services.risk_scoring import RiskContext


def _company(**overrides) -> Company:
    defaults = {
        "cnpj": "11222333000181",
        "razao_social": "EMPRESA TESTE",
        "situacao_cadastral": "ATIVA",
        "source_provider": "minha_receita",
        "source_collected_at": datetime.now(UTC),
        "raw_response": {},
        "data_abertura": None,
        "capital_social": None,
        "cnae_principal_descricao": None,
    }
    defaults.update(overrides)
    return Company(**defaults)


def _ctx(company: Company, **overrides) -> RiskContext:
    defaults = {
        "company": company,
        "expected_activity_description": None,
        "shared_address_company_count": 0,
        "restrictive_matches": [],
        "now": datetime.now(UTC),
    }
    defaults.update(overrides)
    return RiskContext(**defaults)


def _restrictive_entry(**overrides) -> RestrictiveListEntry:
    defaults = {
        "list_type": "ceis",
        "external_id": "1",
        "document": "11222333000181",
        "document_type": "cnpj",
        "name": "X",
        "raw_data": {},
    }
    defaults.update(overrides)
    return RestrictiveListEntry(**defaults)


# --- empresa_recente ---


def test_empresa_recente_triggers_when_within_window():
    company = _company(data_abertura=(datetime.now(UTC) - timedelta(days=10)).date())
    ctx = _ctx(company)

    reason = risk_scoring._rule_empresa_recente(ctx, {"max_months": 6})

    assert reason is not None


def test_empresa_recente_does_not_trigger_when_old():
    company = _company(data_abertura=(datetime.now(UTC) - timedelta(days=3650)).date())
    ctx = _ctx(company)

    assert risk_scoring._rule_empresa_recente(ctx, {"max_months": 6}) is None


def test_empresa_recente_skips_when_no_date():
    ctx = _ctx(_company(data_abertura=None))

    assert risk_scoring._rule_empresa_recente(ctx, {"max_months": 6}) is None


# --- capital_social_irrisorio ---


def test_capital_irrisorio_triggers_below_threshold():
    ctx = _ctx(_company(capital_social=100))

    assert risk_scoring._rule_capital_social_irrisorio(ctx, {"min_capital": 1000}) is not None


def test_capital_irrisorio_does_not_trigger_above_threshold():
    ctx = _ctx(_company(capital_social=50000))

    assert risk_scoring._rule_capital_social_irrisorio(ctx, {"min_capital": 1000}) is None


# --- situacao_cadastral_inativa ---


def test_situacao_inativa_triggers_for_baixada():
    ctx = _ctx(_company(situacao_cadastral="BAIXADA"))

    assert risk_scoring._rule_situacao_cadastral_inativa(ctx, {}) is not None


def test_situacao_inativa_does_not_trigger_for_ativa():
    ctx = _ctx(_company(situacao_cadastral="ATIVA"))

    assert risk_scoring._rule_situacao_cadastral_inativa(ctx, {}) is None


# --- cnae_incompativel ---


def test_cnae_incompativel_triggers_when_no_shared_words():
    company = _company(cnae_principal_descricao="Comércio a varejo de peças automotivas")
    ctx = _ctx(company, expected_activity_description="Consultoria em tecnologia da informação")

    assert risk_scoring._rule_cnae_incompativel(ctx, {}) is not None


def test_cnae_compativel_does_not_trigger_when_words_overlap():
    company = _company(cnae_principal_descricao="Comércio a varejo de peças automotivas")
    ctx = _ctx(company, expected_activity_description="Venda de peças automotivas usadas")

    assert risk_scoring._rule_cnae_incompativel(ctx, {}) is None


def test_cnae_incompativel_skips_when_no_expected_activity():
    company = _company(cnae_principal_descricao="Comércio a varejo de peças automotivas")
    ctx = _ctx(company, expected_activity_description=None)

    assert risk_scoring._rule_cnae_incompativel(ctx, {}) is None


def test_cnae_compativel_via_known_synonym():
    """The reported real-world case: an autoescola's official CNAE wording
    ("Treinamento de condutores") shares zero words with what a user
    actually types, even though it's the exact same business.
    """
    company = _company(cnae_principal_descricao="Treinamento de condutores")
    ctx = _ctx(company, expected_activity_description="Auto escola")

    assert risk_scoring._rule_cnae_incompativel(ctx, {}) is None


def test_cnae_incompativel_still_triggers_when_synonym_group_does_not_apply():
    company = _company(cnae_principal_descricao="Comércio a varejo de peças automotivas")
    ctx = _ctx(company, expected_activity_description="Auto escola")

    assert risk_scoring._rule_cnae_incompativel(ctx, {}) is not None


# --- endereco_compartilhado ---


def test_endereco_compartilhado_triggers_above_threshold():
    ctx = _ctx(_company(), shared_address_company_count=10)

    assert risk_scoring._rule_endereco_compartilhado(ctx, {"threshold": 5}) is not None


def test_endereco_compartilhado_does_not_trigger_at_threshold():
    ctx = _ctx(_company(), shared_address_company_count=5)

    assert risk_scoring._rule_endereco_compartilhado(ctx, {"threshold": 5}) is None


# --- quadro_societario_instavel ---


def test_qsa_instavel_triggers_with_many_recent_changes():
    company = _company()
    now = datetime.now(UTC)
    person = Person(nome="A", cpf_masked="***111111**")
    for i in range(3):
        company.partnerships.append(
            Partnership(person=person, first_seen_at=now - timedelta(days=i))
        )
    ctx = _ctx(company, now=now)

    reason = risk_scoring._rule_quadro_societario_instavel(
        ctx, {"max_changes": 2, "window_months": 12}
    )

    assert reason is not None


def test_qsa_instavel_ignores_changes_outside_window():
    company = _company()
    now = datetime.now(UTC)
    person = Person(nome="A", cpf_masked="***111111**")
    for i in range(3):
        company.partnerships.append(
            Partnership(person=person, first_seen_at=now - timedelta(days=400 + i))
        )
    ctx = _ctx(company, now=now)

    reason = risk_scoring._rule_quadro_societario_instavel(
        ctx, {"max_changes": 2, "window_months": 12}
    )

    assert reason is None


def test_qsa_instavel_counts_endings_too():
    company = _company()
    now = datetime.now(UTC)
    person = Person(nome="A", cpf_masked="***111111**")
    company.partnerships.append(
        Partnership(
            person=person, first_seen_at=now - timedelta(days=400), ended_at=now - timedelta(days=5)
        )
    )
    company.partnerships.append(Partnership(person=person, first_seen_at=now - timedelta(days=1)))
    company.partnerships.append(Partnership(person=person, first_seen_at=now - timedelta(days=1)))

    ctx = _ctx(company, now=now)
    reason = risk_scoring._rule_quadro_societario_instavel(
        ctx, {"max_changes": 2, "window_months": 12}
    )

    assert reason is not None


# --- match_lista_restritiva ---


def test_lista_restritiva_triggers_when_matches_present():
    ctx = _ctx(_company(), restrictive_matches=[_restrictive_entry()])

    assert risk_scoring._rule_match_lista_restritiva(ctx, {}) is not None


def test_lista_restritiva_does_not_trigger_without_matches():
    ctx = _ctx(_company(), restrictive_matches=[])

    assert risk_scoring._rule_match_lista_restritiva(ctx, {}) is None


# --- evaluate() engine ---


def _config(*rules: RuleConfig, version: int = 1) -> RulesConfig:
    return RulesConfig(version=version, rules=list(rules))


def test_evaluate_sums_weights_of_triggered_rules():
    ctx = _ctx(_company(situacao_cadastral="BAIXADA", capital_social=100))
    config = _config(
        RuleConfig(id="situacao_cadastral_inativa", label="X", weight=20),
        RuleConfig(
            id="capital_social_irrisorio", label="Y", weight=10, params={"min_capital": 1000}
        ),
    )

    result = risk_scoring.evaluate(ctx, config)

    assert result.score == 30
    assert result.rules_version == 1
    assert all(r.triggered for r in result.results)


def test_evaluate_skips_disabled_rules():
    ctx = _ctx(_company(situacao_cadastral="BAIXADA"))
    config = _config(
        RuleConfig(id="situacao_cadastral_inativa", label="X", weight=20, enabled=False),
    )

    result = risk_scoring.evaluate(ctx, config)

    assert result.score == 0
    assert result.results == []


def test_evaluate_caps_score_at_100():
    ctx = _ctx(_company(situacao_cadastral="BAIXADA"), restrictive_matches=[_restrictive_entry()])
    config = _config(
        RuleConfig(id="situacao_cadastral_inativa", label="X", weight=20),
        RuleConfig(id="match_lista_restritiva", label="Y", weight=100),
    )

    result = risk_scoring.evaluate(ctx, config)

    assert result.score == 100
