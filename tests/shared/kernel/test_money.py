import pytest

from kart.shared.kernel.money import Money


@pytest.mark.parametrize(
    ("amount_fils", "vat_fils"),
    [
        (1000, 48),  # AED 10.00: 47.62 fils rounds up
        (105, 5),  # AED 1.05: exactly 5 fils
        # VAT is fils / 21, so it never lands exactly on half a fil.
        # These two amounts sit either side of that line.
        (220, 10),  # 21 x 10 + 10: 10.476 fils rounds down
        (221, 11),  # 21 x 10 + 11: 10.524 fils rounds up
        (0, 0),
    ],
)
def test_vat_included_is_five_105ths_rounded_to_the_fil(amount_fils: int, vat_fils: int) -> None:
    assert Money(amount_fils).vat_included() == Money(vat_fils)


def test_amounts_add_up() -> None:
    assert Money(1050) + Money(250) == Money(1300)


def test_a_unit_price_times_a_quantity_is_the_line_amount() -> None:
    assert Money(1999) * 3 == Money(5997)


def test_amounts_compare_by_value() -> None:
    # The Delivery Charge bands compare a Shipment's value against AED 100 and AED 500.
    assert Money(9999) < Money(10000) <= Money(10000) < Money(50001)
    assert max(Money(500), Money(1200), Money(700)) == Money(1200)


def test_a_negative_amount_is_refused() -> None:
    with pytest.raises(ValueError, match="negative"):
        Money(-1)


def test_an_amount_is_immutable() -> None:
    amount = Money(100)
    with pytest.raises(AttributeError):
        amount.fils = 200  # ty: ignore[invalid-assignment]
