"""Decimal helpers for money values.

Business calculations use :class:`decimal.Decimal`. Binary floats are
accepted only at the Excel boundary, then quantized to cents.
"""

import numbers
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTS: Decimal = Decimal("0.01")
AMOUNT_COLUMN: str = "amount"
_AMOUNT_ERROR: str = "Column 'amount' must contain only numbers."


def parse_amount(value: object) -> Decimal:
    """Parse one cell into a two-decimal Decimal.

    Floats go through ``str`` first so ``0.1`` stays ``0.1`` instead of
    the binary expansion. The result is quantized half-up to cents.
    """
    if value is None or isinstance(value, bool):
        raise ValueError(_AMOUNT_ERROR)

    number: Decimal
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, numbers.Integral):
        number = Decimal(int(value))
    elif isinstance(value, numbers.Real):
        number = Decimal(str(value))
    else:
        text: str = str(value).strip()
        if text.lower() in {"", "nan", "none", "<na>", "nat"}:
            raise ValueError(_AMOUNT_ERROR)
        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(_AMOUNT_ERROR) from exc

    if not number.is_finite():
        raise ValueError(_AMOUNT_ERROR)
    return number.quantize(CENTS, rounding=ROUND_HALF_UP)


def format_amount(value: Decimal) -> str:
    """Serialize money as a fixed two-decimal string."""
    quantized: Decimal = value.quantize(CENTS, rounding=ROUND_HALF_UP)
    return f"{quantized:.2f}"
