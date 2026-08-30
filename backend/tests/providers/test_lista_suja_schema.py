from datetime import date

from app.providers.lista_suja_schema import parse_row


def test_parses_cnpj_row_and_strips_duplicated_prefix():
    # Real shape observed from the source PDF: the Empregador cell repeats the
    # CNPJ raiz before the name.
    row = [
        "1",
        "2024",
        "SP",
        "41.297.068 GILBERTO ELENO BATISTA\nDOS SANTOS",
        "41.297.068/0001-61",
        "ROD. PREFEITO JOAQUIM SIMÃO, KM 735, CENTRO, IGARATÁ/SP",
        "2",
        "4399-1/03",
        "15/05/2025",
        "06/10/2025",
    ]

    entry = parse_row(row)

    assert entry.list_type == "trabalho_escravo"
    assert entry.external_id == "1"
    assert entry.document == "41297068000161"
    assert entry.document_type == "cnpj"
    assert entry.name == "GILBERTO ELENO BATISTA DOS SANTOS"
    assert entry.sanction_start_date == date(2025, 5, 15)


def test_parses_cpf_row_without_prefix_stripping():
    row = [
        "8",
        "2024",
        "ES",
        "ABEL PIONA BERNABÉ",
        "076.802.477-30",
        "RODOVIA ES 436, SN, ZONA RURAL, GOVERNADOR LINDENBERG/ES",
        "12",
        "0134-2/00",
        "30/08/2024",
        "09/04/2025",
    ]

    entry = parse_row(row)

    assert entry.document == "07680247730"
    assert entry.document_type == "cpf"
    assert entry.name == "ABEL PIONA BERNABÉ"


def test_strips_footnote_marker_from_name():
    row = [
        "13",
        "2025",
        "MG",
        "ADELSON NERES ALVES (*1)",
        "468.596.401-20",
        "SITIO EXEMPLO, ZONA RURAL, CIDADE/MG",
        "5",
        "0151-2/02",
        "04/11/2025",
        "",
    ]

    entry = parse_row(row)

    assert entry.name == "ADELSON NERES ALVES"


def test_skips_header_row():
    row = ["ID", "Ano da\nação\nfiscal", "UF", "Empregador", "CNPJ/CPF", "Estabelecimento"]

    assert parse_row(row) is None


def test_skips_section_title_row():
    row = ["I- PUBLICAÇÃO DO CADASTRO...", None, None, None, None, None, None, None, None, None]

    assert parse_row(row) is None


def test_skips_row_with_unparseable_document():
    row = ["1", "2024", "SP", "NOME", "documento inválido", "END", "1", "0000-0/00", "", ""]

    assert parse_row(row) is None
