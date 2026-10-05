from billing.invoices.invoice import Invoice
from billing.money.format import money


def render(invoice: Invoice) -> str:
    rows = [f"Invoice {invoice.number}"]
    for line in invoice.lines:
        rows.append(f"  {line.description:<20} {money(line.net())}")
    rows.append(f"  {'Net':<20} {money(invoice.net())}")
    rows.append(f"  {'VAT':<20} {money(invoice.tax())}")
    rows.append(f"  {'Total':<20} {money(invoice.total())}")
    return "\n".join(rows)
