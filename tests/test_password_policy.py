"""Tests unitarios de la política de contraseñas."""

import pytest
from pydantic import ValidationError

from app.core.password_policy import (
    get_password_validation_errors,
    is_password_valid,
)
from app.schemas.auth import UserRegister, ChangePasswordIn


@pytest.mark.parametrize(
    "password,expected_fragment",
    [
        ("short1!", "al menos 8 caracteres"),
        ("alllower1!", "mayúscula"),
        ("ALLUPPER1!", "minúscula"),
        ("NoDigits!!", "número"),
        ("NoSpecial1", "carácter especial"),
        ("Has Space1!", "espacios"),
    ],
)
def test_password_policy_rejects_invalid(password: str, expected_fragment: str):
    errors = get_password_validation_errors(password)
    assert any(expected_fragment in e for e in errors)
    assert not is_password_valid(password)


def test_password_policy_accepts_valid():
    assert is_password_valid("TestPass123!")


def test_user_register_schema_valid_password():
    user = UserRegister(
        email="test@example.com",
        nombre="Test",
        password="Segura99@",
    )
    assert user.password == "Segura99@"


def test_user_register_schema_rejects_weak_password():
    with pytest.raises(ValidationError) as exc:
        UserRegister(
            email="test@example.com",
            nombre="Test",
            password="123456",
        )
    assert "password" in str(exc.value).lower() or any(
        "password" in str(err["loc"]) for err in exc.value.errors()
    )


def test_change_password_schema_accepts_valid():
    data = ChangePasswordIn(
        current_password="OldPass99!",
        new_password="NewPass88@",
    )
    assert data.new_password == "NewPass88@"


def test_change_password_schema_rejects_same_password():
    with pytest.raises(ValidationError):
        ChangePasswordIn(
            current_password="SamePass99!",
            new_password="SamePass99!",
        )
