from phi_br_core.validators import only_digits, validate_cpf


def test_only_digits_removes_punctuation() -> None:
    assert only_digits("CPF 123.456.789-09") == "12345678909"


def test_only_digits_ignores_unicode_digits() -> None:
    assert only_digits("CPF １２3⁴5") == "35"


def test_validate_cpf_accepts_valid_synthetic_number() -> None:
    assert validate_cpf("935.411.347-80") is True


def test_validate_cpf_does_not_raise_for_unicode_digits() -> None:
    assert validate_cpf("935.411.347-8²") is False


def test_validate_cpf_rejects_repeated_digits() -> None:
    assert validate_cpf("000.000.000-00") is False


def test_validate_cpf_rejects_bad_check_digits() -> None:
    assert validate_cpf("935.411.347-81") is False
