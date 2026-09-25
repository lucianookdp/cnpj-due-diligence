import gzip
from datetime import UTC, datetime

import pytest

from app import pgfn_file
from app.models import FederalDebt
from app.services import federal_debt_import, risk_scoring
from app.services.risk_scoring import RiskContext
from tests.services.test_risk_scoring import _company


def _row(cnpj="11.222.333/0001-81", valor="1500.50", **overrides) -> dict:
    row = {
        "CPF_CNPJ": cnpj,
        "TIPO_PESSOA": "Pessoa jurídica",
        "TIPO_DEVEDOR": "Principal",
        "TIPO_SITUACAO_INSCRICAO": "Em cobrança",
        "INDICADOR_AJUIZADO": "NAO",
        "VALOR_CONSOLIDADO": valor,
    }
    row.update(overrides)
    return row


def test_aggregate_sums_collected_company_debt_per_root_only():
    totals = pgfn_file.aggregate(
        [
            _row(),
            _row(cnpj="11.222.333/0002-62", valor="100", INDICADOR_AJUIZADO="SIM"),  # branch
            _row(TIPO_SITUACAO_INSCRICAO="Benefício Fiscal"),  # in an installment plan
            _row(TIPO_DEVEDOR="Corresponsável"),
            _row(cnpj="123.456.789-09", TIPO_PESSOA="Pessoa física"),  # people are skipped
            _row(valor="n/a"),
            # Não Previdenciário spells the same values in capitals.
            _row(cnpj="44.555.666/0001-00", valor="10", TIPO_DEVEDOR="PRINCIPAL"),
        ]
    )
    assert totals == {"11222333": [160050, 2, True], "44555666": [1000, 1, False]}


def _summary(
    rows: int, reference: str = "2026_trimestre_02", min_cents: int = 0, tmp_path=None
) -> bytes:
    totals = {f"{i:08d}": [100_000 + i, 1, i % 2 == 0] for i in range(rows)}
    out = tmp_path / "s.csv.gz"
    pgfn_file.write_summary(totals, reference, min_cents, out)
    return out.read_bytes()


def test_summary_round_trip_and_threshold(tmp_path):
    reference, rows = federal_debt_import.parse_summary(_summary(1500, tmp_path=tmp_path))
    assert reference == "2026_trimestre_02"
    assert len(rows) == 1500
    assert rows[0] == {
        "cnpj_root": "00000000",
        "amount_cents": 100_000,
        "inscriptions": 1,
        "judicial": True,
        "reference": "2026_trimestre_02",
    }


@pytest.mark.parametrize(
    "payload",
    [
        b"not gzip",
        gzip.compress(
            b"# 2026_trimestre_02\ncnpj_root,amount_cents,inscriptions,judicial\n12345678,10,1,1\n"
        ),
        gzip.compress(b"no reference line\n"),
        gzip.compress(
            b"# 2026_trimestre_02\ncnpj_root,amount_cents,inscriptions,judicial\n"
            + b"abc,1,1,1\n" * 2000
        ),
        gzip.compress(
            b"# 2026_trimestre_02\ncnpj_root,amount_cents,inscriptions,judicial\n"
            + b"12345678,1,1,yes\n" * 2000
        ),
    ],
    ids=["not-gzip", "too-few-rows", "no-reference", "bad-root", "bad-flag"],
)
def test_parse_summary_refuses_broken_files(payload):
    with pytest.raises(federal_debt_import.InvalidSummaryError):
        federal_debt_import.parse_summary(payload)


def test_parse_summary_refuses_a_decompression_bomb(monkeypatch):
    monkeypatch.setattr(federal_debt_import, "MAX_DECOMPRESSED_BYTES", 1_000)
    with pytest.raises(federal_debt_import.InvalidSummaryError):
        federal_debt_import.parse_summary(gzip.compress(b"0" * 1_000_000))


def test_replace_all_swaps_the_table(db, tmp_path):
    db.add(
        FederalDebt(
            cnpj_root="99999999", amount_cents=1, inscriptions=1, judicial=False, reference="old"
        )
    )
    db.commit()
    _, rows = federal_debt_import.parse_summary(_summary(1200, tmp_path=tmp_path))

    assert federal_debt_import.replace_all(db, rows) == 1200
    assert db.get(FederalDebt, "99999999") is None
    assert federal_debt_import.status(db) == {"reference": "2026_trimestre_02", "companies": 1200}


def _ctx_with_debt(debt: FederalDebt | None) -> RiskContext:
    return RiskContext(
        company=_company(),
        expected_activity_description=None,
        shared_address_company_count=0,
        restrictive_matches=[],
        now=datetime.now(UTC),
        federal_debt=debt,
    )


def test_divida_ativa_rule_reports_amount_and_source():
    debt = FederalDebt(
        cnpj_root="11222333",
        amount_cents=12_345_678,
        inscriptions=3,
        judicial=True,
        reference="2026_trimestre_02",
    )
    reason = risk_scoring._rule_divida_ativa_uniao(_ctx_with_debt(debt), {"min_reais": 10000})
    assert reason == (
        "R$ 123.456,78 em dívida ativa da União em cobrança (3 inscrição(ões), já em execução fiscal). "
        "Fonte: PGFN, dados de 2º trimestre de 2026"
    )


def test_divida_ativa_rule_ignores_small_or_missing_debt():
    small = FederalDebt(
        cnpj_root="11222333",
        amount_cents=500_000,
        inscriptions=1,
        judicial=False,
        reference="2026_trimestre_02",
    )
    assert (
        risk_scoring._rule_divida_ativa_uniao(_ctx_with_debt(small), {"min_reais": 10000}) is None
    )
    assert risk_scoring._rule_divida_ativa_uniao(_ctx_with_debt(None), {"min_reais": 10000}) is None


def test_build_context_finds_the_debt_by_cnpj_root(db):
    from app.repositories import company_repository
    from tests.services.test_dossier import _raw

    company = company_repository.upsert_from_provider(db, _raw("11222333000181"))
    db.add(
        FederalDebt(
            cnpj_root="11222333",
            amount_cents=5_000_000,
            inscriptions=2,
            judicial=False,
            reference="2026_trimestre_02",
        )
    )
    db.commit()

    ctx = risk_scoring.build_context(db, company, None)
    assert ctx.federal_debt is not None and ctx.federal_debt.amount_cents == 5_000_000


def test_quarter_candidates_walk_back_across_years():
    assert pgfn_file.quarter_candidates(datetime(2026, 2, 1, tzinfo=UTC))[:3] == [
        "2026_trimestre_01",
        "2025_trimestre_04",
        "2025_trimestre_03",
    ]
