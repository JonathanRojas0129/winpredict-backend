"""
Política de contraseñas — reglas compartidas para registro de usuarios.
Validación sin librerías externas; mensajes en español.
"""

import re

# Caracteres especiales permitidos según requisitos de seguridad
SPECIAL_CHARS_PATTERN = re.compile(r"[@#!$%&*\-]")

# Longitud mínima exigida
MIN_PASSWORD_LENGTH = 8

# Claves de reglas para identificar qué validación falló
RULE_MIN_LENGTH = "min_length"
RULE_UPPERCASE = "uppercase"
RULE_LOWERCASE = "lowercase"
RULE_DIGIT = "digit"
RULE_SPECIAL = "special"
RULE_NO_SPACES = "no_spaces"


# Mensajes de error en español, uno por regla
PASSWORD_ERROR_MESSAGES: dict[str, str] = {
    RULE_MIN_LENGTH: "La contraseña debe tener al menos 8 caracteres.",
    RULE_UPPERCASE: "La contraseña debe incluir al menos una letra mayúscula (A-Z).",
    RULE_LOWERCASE: "La contraseña debe incluir al menos una letra minúscula (a-z).",
    RULE_DIGIT: "La contraseña debe incluir al menos un número (0-9).",
    RULE_SPECIAL: (
        "La contraseña debe incluir al menos un carácter especial "
        "(@, #, !, $, %, &, *, -)."
    ),
    RULE_NO_SPACES: "La contraseña no puede contener espacios en blanco.",
}


def check_password_rules(password: str) -> dict[str, bool]:
    """
    Evalúa cada regla de la política y devuelve un mapa regla → cumple (True/False).
    """
    return {
        RULE_MIN_LENGTH: len(password) >= MIN_PASSWORD_LENGTH,
        RULE_UPPERCASE: bool(re.search(r"[A-Z]", password)),
        RULE_LOWERCASE: bool(re.search(r"[a-z]", password)),
        RULE_DIGIT: bool(re.search(r"[0-9]", password)),
        RULE_SPECIAL: bool(SPECIAL_CHARS_PATTERN.search(password)),
        RULE_NO_SPACES: " " not in password and "\t" not in password,
    }


def get_password_validation_errors(password: str) -> list[str]:
    """
    Devuelve la lista de mensajes de error en español para las reglas que no se cumplen.
    Lista vacía si la contraseña es válida.
    """
    rules = check_password_rules(password)
    return [
        PASSWORD_ERROR_MESSAGES[rule_key]
        for rule_key, passed in rules.items()
        if not passed
    ]


def is_password_valid(password: str) -> bool:
    """Indica si la contraseña cumple todas las reglas de la política."""
    return len(get_password_validation_errors(password)) == 0


def enforce_password_policy(password: str) -> str:
    """
    Valida y devuelve la contraseña si cumple la política.
    Lanza ValueError con mensajes en español (para validadores Pydantic).
    """
    errores = get_password_validation_errors(password)
    if errores:
        raise ValueError("; ".join(errores))
    return password


def validate_password_policy(v: str) -> str:
    """Alias reutilizable para validadores Pydantic (UserRegister, ResetPasswordIn, etc.)."""
    return enforce_password_policy(v)
