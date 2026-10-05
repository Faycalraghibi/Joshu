import pytest
from billing.discounts import percent_off
from billing.invoices.invoice import Invoice
from billing.invoices.lines import Line
from billing.invoices.render import render
from billing.money.format import money
from billing.money.rounding import to_cents
from billing.payments.plans import installments
from billing.tax.vat import vat


@pytest.mark.parametrize(
    "amount, cents",
    [
        (2.675, 2.68),
        (1.005, 1.01),
        (0.125, 0.13),
        (2.665, 2.67),
        (1.234, 1.23),
        (-2.675, -2.68),
        (10, 10.0),
        (0.0, 0.0),
    ],
)
def test_to_cents(amount, cents):
    assert to_cents(amount) == pytest.approx(cents, abs=1e-9)


def test_vat_and_lines():
    assert vat(0.125) == pytest.approx(0.03)
    assert Line("x", 2.675).net() == pytest.approx(2.68)


def test_invoice_and_render():
    invoice = Invoice("INV-1", [Line("item", 2.675)])
    assert invoice.net() == pytest.approx(2.68)
    assert invoice.tax() == pytest.approx(0.54)
    assert invoice.total() == pytest.approx(3.22)
    assert "€2.68" in render(invoice)


def test_format_and_discount():
    assert money(1.005) == "€1.01"
    assert percent_off(10.05, 50) == pytest.approx(5.03)


def test_installments_sum_exactly():
    for total, months in [(100.0, 3), (2.675, 2), (0.05, 3)]:
        parts = installments(total, months)
        assert len(parts) == months
        assert round(sum(parts), 2) == to_cents(total)
