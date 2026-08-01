"""Cost-control value contracts."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


class InvalidCost(ValueError):
    pass


def normalized_cost(value: Decimal | int | float | str) -> Decimal:
    try:
        result = Decimal(str(value)).quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidCost("Costo non valido.") from exc
    if result < 0:
        raise InvalidCost("Il costo non puo essere negativo.")
    return result
