import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.providers.receita_schema import parse_receita_payload

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_parses_a_real_receita_payload_shape():
    payload = _load("banco_do_brasil.json")

    data = parse_receita_payload(payload, source_provider="minha_receita")

    assert data.cnpj == "00000000000191"
    assert data.razao_social == "BANCO DO BRASIL SA"
    assert data.situacao_cadastral == "ATIVA"
    assert data.situacao_cadastral_data == date(2005, 11, 3)
    assert data.data_abertura == date(1966, 8, 1)
    assert data.capital_social == Decimal(120000000000)
    assert data.natureza_juridica_codigo == "2038"
    assert data.natureza_juridica_descricao == "Sociedade de Economia Mista"
    assert data.cnae_principal_codigo == "6422100"
    assert data.uf == "DF"
    assert data.cep == "70040912"
    assert data.source_provider == "minha_receita"


def test_parses_secondary_cnaes():
    payload = _load("banco_do_brasil.json")

    data = parse_receita_payload(payload, source_provider="minha_receita")

    assert len(data.cnaes_secundarios) >= 1
    assert data.cnaes_secundarios[0].codigo == "6499999"


def test_parses_partners_with_masked_cpf():
    payload = _load("banco_do_brasil.json")

    data = parse_receita_payload(payload, source_provider="minha_receita")

    assert len(data.partners) == 3
    first = data.partners[0]
    assert first.nome == "ALAN CARLOS GUEDES DE OLIVEIRA"
    assert first.documento == "***550179**"
    assert first.tipo_socio == "pessoa_fisica"
    assert first.qualificacao == "Diretor"
    assert first.faixa_etaria == "Entre 41 a 50 anos"
    assert first.entrada_sociedade == date(2023, 5, 17)


def test_parses_pessoa_juridica_partner():
    payload = _load("banco_do_brasil.json")
    payload["qsa"] = [
        {
            "nome_socio": "HOLDING EXEMPLO LTDA",
            "cnpj_cpf_do_socio": "11222333000181",
            "qualificacao_socio": "Sócio",
            "faixa_etaria": None,
            "identificador_de_socio": 1,
        }
    ]

    data = parse_receita_payload(payload, source_provider="minha_receita")

    assert len(data.partners) == 1
    assert data.partners[0].tipo_socio == "pessoa_juridica"
    assert data.partners[0].documento == "11222333000181"


def test_missing_optional_fields_default_to_none():
    payload = _load("banco_do_brasil.json")
    payload["nome_fantasia"] = ""
    payload["cnaes_secundarios"] = []
    payload["qsa"] = []

    data = parse_receita_payload(payload, source_provider="brasil_api")

    assert data.nome_fantasia is None
    assert data.cnaes_secundarios == []
    assert data.partners == []
