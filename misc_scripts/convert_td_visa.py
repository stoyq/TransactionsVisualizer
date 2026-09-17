"""Convert copied TD Visa transactions into date, description, debit, credit rows.

Run with no arguments to convert the default source into a sibling file named
manual_copied_from_pdf_converted.csv. Optional arguments: input_csv output_csv.

Example source CSV (one column, with descriptions spanning multiple rows):
    JAN 2
    JAN 5
    $99.00
    UBC RECREATION: ONLINE RE
    VANCOUVER
    JAN 3
    JAN 5
    -$25.00
    EXAMPLE REFUND
    VANCOUVER

Transformed CSV (date, description, debit, credit; no header row):
    01/02/2026,UBC RECREATION: ONLINE RE VANCOUVER,99.00,
    01/03/2026,EXAMPLE REFUND VANCOUVER,,25.00

The first date is formatted as MM/DD/2026 and the posting date is discarded. Description lines
are joined with spaces. Negative amounts become positive credits; the unused
debit or credit column is left blank.
"""

import argparse
import csv
import re
from datetime import date as calendar_date
from decimal import Decimal
from pathlib import Path

# By default, this script runs on data/raw/2026/TD/Visa/manual_copied_from_pdf.csv
# because its PDF-copied transactions span multiple rows and include posting dates;
# convert them into one row per transaction with date, description, debit, and credit.
DEFAULT_INPUT = (
    Path(__file__).resolve().parents[1]
    / "data/raw/2026/TD/Visa/manual_copied_from_pdf.csv"
)
DATE = re.compile(r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2}")
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
AMOUNT = re.compile(r"[+-]?\$?(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}")


def convert(source: Path, destination: Path) -> int:
    """Read and validate source transactions, write the CSV, and return its row count.

    Raise ValueError for malformed input or matching input and output paths.
    Parse every transaction before opening the destination for writing.
    """
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output must be different files.")

    # Read the single-column CSV, ignoring blank lines and unwrapping quoted cells.
    lines = []
    with source.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if not row or not any(cell.strip() for cell in row):
                continue
            if len(row) != 1:
                raise ValueError(f"Expected one source column, got {row!r}")
            lines.extend(line.strip() for line in row[0].splitlines() if line.strip())

    # Each transaction starts with a transaction date, posting date, and amount.
    transactions = []
    index = 0
    while index < len(lines):
        if not DATE.fullmatch(lines[index]):
            raise ValueError(f"Expected transaction date, got {lines[index]!r}")
        date = lines[index]
        # All transactions belong to 2026; validate and zero-pad the month and day.
        month, day = date.split()
        formatted_date = calendar_date(2026, MONTHS.index(month) + 1, int(day)).strftime(
            "%m/%d/%Y"
        )
        # Validate the posting date, but omit it from the output.
        if index + 2 >= len(lines) or not DATE.fullmatch(lines[index + 1]):
            raise ValueError(f"Missing posting date or amount after {date!r}")
        amount_text = lines[index + 2]
        if not AMOUNT.fullmatch(amount_text):
            raise ValueError(f"Invalid amount after {date!r}: {amount_text!r}")
        amount = Decimal(amount_text.replace("$", "").replace(",", ""))
        index += 3
        # Collect description lines until the next transaction date or end of file.
        description = []
        while index < len(lines) and not DATE.fullmatch(lines[index]):
            description.append(lines[index])
            index += 1
        if not description:
            raise ValueError(f"Missing description after {date!r}")
        # Keep exact decimal amounts and place negative values in the credit column.
        debit = f"{amount:.2f}" if amount >= 0 else ""
        credit = f"{abs(amount):.2f}" if amount < 0 else ""
        transactions.append((formatted_date, " ".join(description), debit, credit))

    # Write four columns without headers only after the entire input is validated.
    with destination.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(transactions)
    return len(transactions)


def main() -> None:
    """Parse optional file paths, run the conversion, and report the output location."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("output_csv", nargs="?", type=Path)
    args = parser.parse_args()
    # Default to a sibling output file so the original CSV is preserved.
    destination = args.output_csv or args.input_csv.with_name(
        f"{args.input_csv.stem}_converted.csv"
    )
    count = convert(args.input_csv, destination)
    print(f"Wrote {count} transactions to {destination}")


if __name__ == "__main__":
    main()
