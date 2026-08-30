import pytest

from app.core.document import InvalidDocumentError, mask_cpf, normalize_document


def test_normalizes_formatted_cnpj():
    doc, doc_type = normalize_document("41.297.068/0001-61")
    assert doc == "41297068000161"
    assert doc_type == "cnpj"


def test_normalizes_formatted_cpf():
    doc, doc_type = normalize_document("076.802.477-30")
    assert doc == "07680247730"
    assert doc_type == "cpf"


def test_rejects_wrong_digit_count():
    with pytest.raises(InvalidDocumentError):
        normalize_document("123")


def test_mask_cpf_reproduces_receita_format():
    assert mask_cpf("07680247730") == "***802477**"


def test_mask_cpf_rejects_wrong_length():
    with pytest.raises(InvalidDocumentError):
        mask_cpf("123")
