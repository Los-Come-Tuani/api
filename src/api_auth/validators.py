from django.core.exceptions import ValidationError

########################################################################################


class ComplexityPasswordValidator:
    """Al menos una mayúscula y un número (RF-S-05)."""

    def validate(self, password: str, user: object | None = None) -> None:  # ruff: ignore[no-self-use, unused-method-argument]
        if any(c.isupper() for c in password) and any(c.isdigit() for c in password):
            return

        raise ValidationError(
            "Esta contraseña debe tener al menos una mayúscula y un número.",
            code="password_too_simple",
        )

    def get_help_text(self) -> str:  # ruff: ignore[no-self-use]
        return "Tu contraseña debe tener al menos una mayúscula y un número."
