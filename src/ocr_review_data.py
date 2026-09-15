"""Read-only source loading and in-memory OCR review helpers."""

from pathlib import Path

import pandas as pd

EDITABLE_FIELDS = (
    "store_name",
    "description",
    "receipt_code",
    "amount",
    "date",
    "combined_text",
    "parse_valid",
)


def load_summary(path: Path) -> pd.DataFrame:
    # Preserve receipt identifiers, empty cells, and the original CSV values.
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if "source_image" not in frame.columns:
        raise ValueError("The summary CSV must contain a source_image column.")
    if frame.empty:
        raise ValueError("The summary CSV has no rows to review.")
    return frame


def annotated_image(directory: Path, source_image: str) -> Path | None:
    """Resolve PaddleOCR's annotated filename, confined to the image directory."""
    directory = directory.resolve()
    name = Path(source_image).name
    for candidate in (f"{Path(name).stem}_ocr_res_img{Path(name).suffix}", name):
        path = (directory / candidate).resolve()
        if path.parent == directory and path.is_file():
            return path
    return None


def apply_edits(frame: pd.DataFrame, row: int, values: dict[str, str]) -> pd.DataFrame:
    updated = frame.copy(deep=True)
    for field, value in values.items():
        if field in EDITABLE_FIELDS and field in updated.columns:
            updated.at[row, field] = value
    return updated


def export_csv(frame: pd.DataFrame) -> bytes:
    """Return a download payload; never write to the source path."""
    return frame.to_csv(index=False).encode("utf-8-sig")


def table_view(frame: pd.DataFrame) -> pd.DataFrame:
    view = frame.copy(deep=True)
    for column in (
        "amount",
        "store_confidence",
        "description_confidence",
        "mean_confidence",
        "detected_text_count",
    ):
        if column in view:
            # Keep any uncorrected OCR text visible instead of replacing it with NaN.
            try:
                view[column] = pd.to_numeric(view[column].replace("", None), errors="raise")
            except ValueError:
                pass
    return view
