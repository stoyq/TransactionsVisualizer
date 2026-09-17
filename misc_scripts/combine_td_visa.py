"""Combine seven TD Visa CSVs into one eight-column CSV with headers.

Run with: python misc_scripts/combine_td_visa.py
Customize INPUT_FILES and OUTPUT_FILE below to change the files being combined.
Rows retain their input order, including duplicates. The fifth column in account
activity exports is discarded.
All rows use td_visa as the data source. Normalized descriptions initially match
the original descriptions; category and subcategory are left blank.
"""

import csv
from pathlib import Path

# Combine the six bank exports with the converted PDF transactions to collect
# the available 2026 Visa transactions in one consistent eight-column file.
VISA_FOLDER = Path(__file__).resolve().parents[1] / "data/raw/2026/TD/Visa"
INPUT_FILES = [
    VISA_FOLDER / "accountactivity.csv",
    VISA_FOLDER / "accountactivity (1).csv",
    VISA_FOLDER / "accountactivity (2).csv",
    VISA_FOLDER / "accountactivity (3).csv",
    VISA_FOLDER / "accountactivity (4).csv",
    VISA_FOLDER / "accountactivity (5).csv",
    VISA_FOLDER / "manual_copied_from_pdf_converted.csv",
]
OUTPUT_FILE = VISA_FOLDER / "combined_2026_visa.csv"
HEADERS = [
    "date",
    "data_source",
    "description",
    "description_normalized",
    "debit",
    "credit",
    "category",
    "subcategory",
]


def combine(input_files: list[Path], output_file: Path) -> int:
    """Map four- or five-column inputs to eight columns; return the transaction count."""
    if any(source.resolve() == output_file.resolve() for source in input_files):
        raise ValueError("The output file must not be one of the input files.")

    # Read every input before opening the output, so invalid input cannot truncate it.
    rows = []
    for source in input_files:
        with source.open(encoding="utf-8-sig", newline="") as handle:
            for row_number, row in enumerate(csv.reader(handle), start=1):
                if not row or not any(cell.strip() for cell in row):
                    continue
                if len(row) not in (4, 5):
                    raise ValueError(
                        f"{source.name}, row {row_number}: expected 4 or 5 columns, "
                        f"got {len(row)}"
                    )
                # Keep date, description, debit, and credit; discard the balance column.
                date, description, debit, credit = row[:4]
                rows.append(
                    [date, "td_visa", description, description, debit, credit, "", ""]
                )

    # Write the column headers followed by the transactions, preserving CSV quoting.
    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    """Combine the configured input files and report the generated file."""
    count = combine(INPUT_FILES, OUTPUT_FILE)
    print(f"Wrote {count} transactions from {len(INPUT_FILES)} files to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
