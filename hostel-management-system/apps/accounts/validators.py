from django.core.exceptions import ValidationError


class LetterAndDigitValidator:
    """SEC-REQ-2: password must contain at least one letter and one digit."""

    def validate(self, password, user=None):
        if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)):
            raise ValidationError("Password must contain at least one letter and one digit.",
                                  code="password_no_letter_digit")

    def get_help_text(self):
        return "Your password must contain at least one letter and one digit."
