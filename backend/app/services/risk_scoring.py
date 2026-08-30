import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import yaml
from sqlalchemy.orm import Session

from app.core.rules_config import RuleConfig, RulesConfig
from app.models import Company, RestrictiveListEntry
from app.repositories import graph_repository
from app.services import restrictive_list_matching

_CNAE_SYNONYMS_PATH = Path(__file__).resolve().parent.parent / "rules" / "cnae_synonyms.yaml"

# A rule engine month is treated as 30 days throughout — this is a risk
# heuristic, not a legal/financial calculation, so calendar precision isn't
# worth the extra dependency (dateutil) it would take to get right.
_DAYS_PER_MONTH = 30

_STOPWORDS = {
    "de",
    "da",
    "do",
    "das",
    "dos",
    "e",
    "em",
    "para",
    "com",
    "a",
    "o",
    "as",
    "os",
    "por",
    "sem",
    "ou",
    "um",
    "uma",
}


@dataclass
class RiskContext:
    company: Company
    expected_activity_description: str | None
    shared_address_company_count: int
    restrictive_matches: list[RestrictiveListEntry]
    now: datetime


@dataclass
class RuleResult:
    rule_id: str
    label: str
    weight: int
    triggered: bool
    reason: str | None


@dataclass
class RiskScore:
    score: int
    rules_version: int
    results: list[RuleResult]


class RuleFn(Protocol):
    def __call__(self, ctx: RiskContext, params: dict) -> str | None: ...


def _to_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z]+", _normalize(text))
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 2}


@lru_cache
def _load_cnae_synonym_groups() -> list[list[str]]:
    with open(_CNAE_SYNONYMS_PATH) as f:
        data = yaml.safe_load(f)
    return data["groups"]


def _cnae_synonym_expansion(text: str) -> set[str]:
    """Every token from every phrase in a synonym group, for each group that
    has at least one phrase appearing in `text` — see cnae_synonyms.yaml.
    """
    normalized = _normalize(text)
    expansion: set[str] = set()
    for group in _load_cnae_synonym_groups():
        if any(_normalize(phrase) in normalized for phrase in group):
            for phrase in group:
                expansion |= _tokenize(phrase)
    return expansion


_MIN_ROOT_LEN = 5


def _shares_word_root(a: set[str], b: set[str], min_len: int = _MIN_ROOT_LEN) -> bool:
    """True if any token in `a` shares a min_len-character prefix with any
    token in `b`.

    Handles Portuguese suffix variation a synonym list can't reasonably
    enumerate: "atacado" vs "atacadista", "varejo" vs "varejista",
    "comércio" vs "comercial" all share a long enough root that an exact
    keyword-overlap check (or even the synonym expansion above) treats them
    as completely unrelated words. Real language-aware stemming would be
    more precise, but pulling in a stemmer library for one rule isn't worth
    it when a shared-prefix check already catches the common cases cheaply.
    """
    prefixes_a = {t[:min_len] for t in a if len(t) >= min_len}
    prefixes_b = {t[:min_len] for t in b if len(t) >= min_len}
    return not prefixes_a.isdisjoint(prefixes_b)


def _rule_empresa_recente(ctx: RiskContext, params: dict) -> str | None:
    if ctx.company.data_abertura is None:
        return None
    max_months = params.get("max_months", 6)
    cutoff = ctx.now.date() - timedelta(days=max_months * _DAYS_PER_MONTH)
    if ctx.company.data_abertura > cutoff:
        return (
            f"Aberta em {ctx.company.data_abertura.strftime('%d/%m/%Y')}, "
            f"há menos de {max_months} meses"
        )
    return None


def _rule_capital_social_irrisorio(ctx: RiskContext, params: dict) -> str | None:
    min_capital = Decimal(str(params.get("min_capital", 1000)))
    if ctx.company.capital_social is not None and ctx.company.capital_social < min_capital:
        return f"Capital social de R$ {ctx.company.capital_social} é inferior a R$ {min_capital}"
    return None


def _rule_situacao_cadastral_inativa(ctx: RiskContext, _params: dict) -> str | None:
    if ctx.company.situacao_cadastral.upper() != "ATIVA":
        return f"Situação cadastral é '{ctx.company.situacao_cadastral}', não ATIVA"
    return None


def _rule_cnae_incompativel(ctx: RiskContext, _params: dict) -> str | None:
    if not ctx.expected_activity_description or not ctx.company.cnae_principal_descricao:
        return None
    expected_tokens = _tokenize(ctx.expected_activity_description)
    expected_tokens |= _cnae_synonym_expansion(ctx.expected_activity_description)
    cnae_tokens = _tokenize(ctx.company.cnae_principal_descricao)
    if (
        expected_tokens
        and cnae_tokens
        and expected_tokens.isdisjoint(cnae_tokens)
        and not _shares_word_root(expected_tokens, cnae_tokens)
    ):
        return (
            f"Atividade esperada '{ctx.expected_activity_description}' não tem palavras em "
            f"comum com o CNAE principal '{ctx.company.cnae_principal_descricao}', mesmo "
            "considerando termos equivalentes conhecidos"
        )
    return None


def _rule_endereco_compartilhado(ctx: RiskContext, params: dict) -> str | None:
    threshold = params.get("threshold", 5)
    if ctx.shared_address_company_count > threshold:
        return (
            f"Endereço compartilhado por {ctx.shared_address_company_count} empresas "
            f"(limite: {threshold})"
        )
    return None


def _rule_quadro_societario_instavel(ctx: RiskContext, params: dict) -> str | None:
    max_changes = params.get("max_changes", 2)
    window_months = params.get("window_months", 12)
    cutoff = ctx.now - timedelta(days=window_months * _DAYS_PER_MONTH)

    changes = 0
    for partnership in ctx.company.partnerships:
        if _to_aware(partnership.first_seen_at) >= cutoff:
            changes += 1
        if partnership.ended_at is not None and _to_aware(partnership.ended_at) >= cutoff:
            changes += 1

    if changes > max_changes:
        return (
            f"Quadro societário teve {changes} mudanças nos últimos {window_months} meses "
            f"(limite: {max_changes})"
        )
    return None


def _rule_match_lista_restritiva(ctx: RiskContext, _params: dict) -> str | None:
    if not ctx.restrictive_matches:
        return None
    list_names = ", ".join(sorted({m.list_type.upper() for m in ctx.restrictive_matches}))
    return f"Presença em lista(s) restritiva(s): {list_names}"


_RULE_FUNCTIONS: dict[str, RuleFn] = {
    "empresa_recente": _rule_empresa_recente,
    "capital_social_irrisorio": _rule_capital_social_irrisorio,
    "situacao_cadastral_inativa": _rule_situacao_cadastral_inativa,
    "cnae_incompativel": _rule_cnae_incompativel,
    "endereco_compartilhado": _rule_endereco_compartilhado,
    "quadro_societario_instavel": _rule_quadro_societario_instavel,
    "match_lista_restritiva": _rule_match_lista_restritiva,
}


def _evaluate_rule(ctx: RiskContext, rule: RuleConfig) -> RuleResult:
    fn = _RULE_FUNCTIONS[rule.id]
    reason = fn(ctx, rule.params)
    return RuleResult(
        rule_id=rule.id,
        label=rule.label,
        weight=rule.weight,
        triggered=reason is not None,
        reason=reason,
    )


def evaluate(ctx: RiskContext, config: RulesConfig) -> RiskScore:
    results = [_evaluate_rule(ctx, rule) for rule in config.rules if rule.enabled]
    total = sum(r.weight for r in results if r.triggered)
    return RiskScore(score=min(total, 100), rules_version=config.version, results=results)


def build_context(
    db: Session, company: Company, expected_activity_description: str | None
) -> RiskContext:
    shared_count = 0
    if company.address_key:
        counts = graph_repository.count_companies_by_address_key(db, {company.address_key})
        shared_count = counts.get(company.address_key, 0)

    matches = list(restrictive_list_matching.match_by_cnpj(db, company.cnpj))
    for partnership in company.partnerships:
        if partnership.ended_at is None:
            matches.extend(
                restrictive_list_matching.match_by_masked_cpf(db, partnership.person.cpf_masked)
            )

    return RiskContext(
        company=company,
        expected_activity_description=expected_activity_description,
        shared_address_company_count=shared_count,
        restrictive_matches=matches,
        now=datetime.now(UTC),
    )
