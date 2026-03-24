import subprocess
from datetime import date
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


def get_git_hash() -> str:
    """Return the short git commit hash of the running deployment.

    Falls back to "unknown" if git is not available (e.g. in some CI environments).
    """
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Date presets
# ---------------------------------------------------------------------------

DATE_PRESETS: dict[str, tuple[date, date]] = {
    "pre_mds": (date(2025, 1, 1), date(2025, 8, 25)),
    "mds": (date(2025, 8, 26), date(2025, 12, 31)),
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_data(local_path: Path, gsheet_id: str, gsheet_gid: str) -> tuple[pd.DataFrame, str]:
    """Load transactions CSV from local disk if available, otherwise from Google Sheets.

    Parameters
    ----------
    local_path:  Path to the local CSV file.
    gsheet_id:   Google Sheets document ID (from the sheet URL).
    gsheet_gid:  Google Sheets tab ID (from the sheet URL; "0" = first tab).

    Returns
    -------
    A tuple of (DataFrame, source_tag) where source_tag is "local" or "google_sheets".
    """
    if Path(local_path).exists():
        return pd.read_csv(local_path, parse_dates=["date"]), "local"

    # Google Sheets CSV export — sheet must be shared as "Anyone with the link"
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={gsheet_gid}"
    return pd.read_csv(url, parse_dates=["date"]), "google_sheets"


# ---------------------------------------------------------------------------
# Data filtering
# ---------------------------------------------------------------------------


def filter_by_date(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Return rows where the date column falls within [start, end] (inclusive).

    The returned DataFrame has a clean 0-based index so DataGrid's positional
    row tracking is always consistent with the data it receives.
    """
    return df.loc[df["date"].dt.date.between(start, end)].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Chart data helpers
# ---------------------------------------------------------------------------


def aggregate_spending(df: pd.DataFrame) -> pd.DataFrame:
    """Group debit transactions by merchant, returning total spend and count.

    Rows where ``debit`` is NaN (i.e. credits / income) are excluded.

    Returns a DataFrame with columns: description_normalized, total, count.
    """
    return (
        df.loc[df["debit"].notna()]
        .groupby("description_normalized", as_index=False)
        .agg(total=("debit", "sum"), count=("debit", "count"))
    )


def build_daily_heatmap_df(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate debit transactions to one row per day for the calendar heatmap.

    Each row contains:
    - date         – the calendar date
    - total        – sum of all debits that day
    - top_label    – "(of N transactions)" for display in the tooltip header
    - top_1/2/3    – the three largest individual transactions formatted as
                     "Merchant  $amount", or "" when fewer than three exist

    Rows where ``debit`` is NaN are excluded before aggregation.
    """
    debits = df.loc[df["debit"].notna()].copy()

    def _day_summary(grp: pd.DataFrame) -> pd.Series:
        top = grp.nlargest(3, "debit").reset_index(drop=True)
        n = len(grp)
        result: dict = {
            "total": grp["debit"].sum(),
            "top_label": f"(of {n} transaction{'s' if n != 1 else ''})",
        }
        for i in range(3):
            if i < len(top):
                result[f"top_{i + 1}"] = (
                    f"{top.loc[i, 'description_normalized']}  ${top.loc[i, 'debit']:,.2f}"
                )
            else:
                result[f"top_{i + 1}"] = ""
        return pd.Series(result)

    return debits.groupby("date").apply(_day_summary, include_groups=False).reset_index()


def get_sort_order(totals_df: pd.DataFrame) -> list[str]:
    """Return merchant names sorted by total spend descending (for chart y-axis)."""
    return totals_df.sort_values("total", ascending=False)["description_normalized"].tolist()


# ---------------------------------------------------------------------------
# Preset matching
# ---------------------------------------------------------------------------


def match_preset(
    start: date,
    end: date,
    presets: dict[str, tuple[date, date]] = DATE_PRESETS,
) -> str | None:
    """Return the preset key whose date range exactly matches (start, end), or None."""
    for key, (ps, pe) in presets.items():
        if start == ps and end == pe:
            return key
    return None
