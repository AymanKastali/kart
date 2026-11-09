from dataclasses import dataclass

VAT_RATE_PERCENT = 5


@dataclass(frozen=True, slots=True, order=True)
class Money:
    """An amount in AED, held as a whole number of fils (1 AED = 100 fils)."""

    fils: int

    def __post_init__(self) -> None:
        if self.fils < 0:
            msg = f"An amount cannot be negative: {self.fils} fils"
            raise ValueError(msg)

    def __add__(self, other: Money) -> Money:
        return Money(self.fils + other.fils)

    def __mul__(self, quantity: int) -> Money:
        return Money(self.fils * quantity)

    def vat_included(self) -> Money:
        """The VAT inside this VAT-inclusive amount: amount x 5/105, rounded half-up to the fil."""
        numerator = self.fils * VAT_RATE_PERCENT
        denominator = 100 + VAT_RATE_PERCENT
        return Money((2 * numerator + denominator) // (2 * denominator))
