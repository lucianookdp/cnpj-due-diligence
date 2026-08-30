from datetime import date

from app.providers.portal_transparencia_schema import (
    parse_ceis_record,
    parse_cepim_record,
    parse_cnep_record,
    parse_leniencia_record,
)


def _ceis_record(**overrides) -> dict:
    record = {
        "id": 12345,
        "dataInicioSancao": "01/03/2024",
        "dataFimSancao": "01/03/2026",
        "tipoSancao": {"descricaoResumida": "Suspensão temporária de participação em licitação"},
        "orgaoSancionador": {"nome": "Tribunal de Contas da União"},
        "sancionado": {"nome": "EMPRESA EXEMPLO LTDA", "codigoFormatado": "11.222.333/0001-81"},
        "pessoa": {"cpfFormatado": None, "cnpjFormatado": "11.222.333/0001-81"},
    }
    record.update(overrides)
    return record


def test_parses_ceis_record():
    entry = parse_ceis_record(_ceis_record())

    assert entry.list_type == "ceis"
    assert entry.external_id == "12345"
    assert entry.document == "11222333000181"
    assert entry.document_type == "cnpj"
    assert entry.name == "EMPRESA EXEMPLO LTDA"
    assert entry.reason == "Suspensão temporária de participação em licitação"
    assert entry.source_org == "Tribunal de Contas da União"
    assert entry.sanction_start_date == date(2024, 3, 1)
    assert entry.sanction_end_date == date(2026, 3, 1)


def test_parses_cnep_record_with_cpf_sancionado():
    record = _ceis_record(sancionado={"nome": "FULANO DE TAL", "codigoFormatado": "076.802.477-30"})

    entry = parse_cnep_record(record)

    assert entry.list_type == "cnep"
    assert entry.document == "07680247730"
    assert entry.document_type == "cpf"


def test_ceis_record_with_unparseable_document_returns_none():
    record = _ceis_record(sancionado={"nome": "X", "codigoFormatado": "123"})

    assert parse_ceis_record(record) is None


def test_ceis_record_missing_sancionado_returns_none():
    record = _ceis_record(sancionado=None)

    assert parse_ceis_record(record) is None


def test_decodes_leaked_js_unicode_escape_in_name():
    # Real artifact observed from the live API: an en-dash comes through as
    # a literal "%U2013" instead of "–".
    record = _ceis_record(
        sancionado={"nome": "RADIAL PNEUS %U2013 ME", "codigoFormatado": "11.222.333/0001-81"}
    )

    entry = parse_ceis_record(record)

    assert entry.name == "RADIAL PNEUS – ME"


def test_parses_cepim_record():
    record = {
        "id": 999,
        "motivo": "Prestação de contas rejeitada",
        "orgaoSuperior": {"nome": "Ministério da Saúde"},
        "pessoaJuridica": {"nome": "ONG EXEMPLO", "cnpjFormatado": "22.333.444/0001-92"},
        "convenio": {"codigo": "123456"},
    }

    entry = parse_cepim_record(record)

    assert entry.list_type == "cepim"
    assert entry.document == "22333444000192"
    assert entry.name == "ONG EXEMPLO"
    assert entry.reason == "Prestação de contas rejeitada"
    assert entry.source_org == "Ministério da Saúde"


def test_parses_leniencia_record_with_multiple_sanctioned_companies():
    record = {
        "id": 42,
        "situacaoAcordo": "Vigente",
        "orgaoResponsavel": "CGU",
        "dataInicioAcordo": "10/01/2023",
        "dataFimAcordo": "10/01/2028",
        "sancoes": [
            {"razaoSocial": "EMPRESA A LTDA", "cnpjFormatado": "11.111.111/0001-11"},
            {"razaoSocial": "EMPRESA B LTDA", "cnpjFormatado": "22.222.222/0001-22"},
        ],
    }

    entries = parse_leniencia_record(record)

    assert len(entries) == 2
    assert entries[0].external_id == "42:0"
    assert entries[0].document == "11111111000111"
    assert entries[1].external_id == "42:1"
    assert entries[1].document == "22222222000122"
    assert all(e.list_type == "leniencia" for e in entries)
    assert all(e.reason == "Vigente" for e in entries)


def test_leniencia_record_skips_companies_with_unparseable_document():
    record = {
        "id": 42,
        "situacaoAcordo": "Vigente",
        "orgaoResponsavel": "CGU",
        "dataInicioAcordo": None,
        "dataFimAcordo": None,
        "sancoes": [{"razaoSocial": "EMPRESA A", "cnpjFormatado": None}],
    }

    assert parse_leniencia_record(record) == []
