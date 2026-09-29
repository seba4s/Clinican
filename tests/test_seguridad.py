"""PIN: validación y hash."""

import pytest

from clinican.dominio import seguridad
from clinican.dominio.errores import DatoInvalido


@pytest.mark.parametrize("pin", ["1234", "12345", "123456"])
def test_pin_valido(pin):
    assert seguridad.validar_pin(pin) == pin


@pytest.mark.parametrize("pin", ["", "123", "1234567", "12a4", "12 34", "abcd", None])
def test_pin_invalido(pin):
    with pytest.raises(DatoInvalido):
        seguridad.validar_pin(pin)


def test_hash_con_sal_propia():
    h1, s1 = seguridad.generar_hash("1234")
    h2, s2 = seguridad.generar_hash("1234")
    assert s1 != s2 and h1 != h2
    assert "1234" not in h1
    assert seguridad.verificar_pin("1234", h1, s1)
    assert not seguridad.verificar_pin("4321", h1, s1)
    assert not seguridad.verificar_pin("abc", h1, s1)
