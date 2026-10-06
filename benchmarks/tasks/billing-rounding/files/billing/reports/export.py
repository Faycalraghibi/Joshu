import csv
import io
from typing import Iterable

from billing.invoices.invoice import Invoice


def to_csv(invoices: Iterable[Invoice]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["number", "net", "vat", "total"])
    for i in invoices:
        writer.writerow([i.number, f"{i.net():.2f}", f"{i.tax():.2f}", f"{i.total():.2f}"])
    return out.getvalue()
