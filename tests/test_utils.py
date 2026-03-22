from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from utils import (
    DATE_PRESETS,
    aggregate_spending,
    filter_by_date,
    get_git_hash,
    get_sort_order,
    load_data,
    match_preset,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_df():
    """A small transactions DataFrame that mirrors the real schema."""
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-10", "2025-03-15", "2025-09-01", "2025-09-20"]),
            "description_normalized": ["Grocery", "Grocery", "Coffee", "Transport"],
            "debit": [50.0, 30.0, 5.0, None],  # None = credit / income row
            "credit": [None, None, None, 100.0],
        }
    )


# ---------------------------------------------------------------------------
# load_data
# ---------------------------------------------------------------------------


class TestLoadData:
    def test_loads_local_file(self, tmp_path, sample_df):
        """Should load from local CSV when the file exists."""
        csv_path = tmp_path / "transactions.csv"
        sample_df.to_csv(csv_path, index=False)

        df, source = load_data(csv_path, gsheet_id="unused", gsheet_gid="0")

        assert source == "local"
        assert len(df) == len(sample_df)

    def test_local_file_parses_dates(self, tmp_path, sample_df):
        """Date column should come back as datetime, not raw strings."""
        csv_path = tmp_path / "transactions.csv"
        sample_df.to_csv(csv_path, index=False)

        df, _ = load_data(csv_path, gsheet_id="unused", gsheet_gid="0")

        assert pd.api.types.is_datetime64_any_dtype(df["date"])

    def test_falls_back_to_google_sheets_when_no_local_file(self, tmp_path, sample_df):
        """Should fall back to Google Sheets when the local file does not exist."""
        missing_path = tmp_path / "does_not_exist.csv"

        with patch("utils.pd.read_csv", return_value=sample_df) as mock_read:
            df, source = load_data(missing_path, gsheet_id="abc123", gsheet_gid="42")

        assert source == "google_sheets"
        called_url = mock_read.call_args[0][0]
        assert "abc123" in called_url
        assert "42" in called_url

    def test_google_sheets_url_contains_export_format(self, tmp_path, sample_df):
        """The constructed URL should use the CSV export endpoint."""
        missing_path = tmp_path / "does_not_exist.csv"

        with patch("utils.pd.read_csv", return_value=sample_df) as mock_read:
            load_data(missing_path, gsheet_id="SHEET_ID", gsheet_gid="999")

        called_url = mock_read.call_args[0][0]
        assert "export?format=csv" in called_url
        assert "gid=999" in called_url


# ---------------------------------------------------------------------------
# filter_by_date
# ---------------------------------------------------------------------------


class TestFilterByDate:
    def test_returns_rows_within_range(self, sample_df):
        result = filter_by_date(sample_df, date(2025, 1, 1), date(2025, 6, 30))
        assert len(result) == 2

    def test_inclusive_start_bound(self, sample_df):
        result = filter_by_date(sample_df, date(2025, 1, 10), date(2025, 6, 30))
        assert len(result) == 2

    def test_inclusive_end_bound(self, sample_df):
        result = filter_by_date(sample_df, date(2025, 1, 1), date(2025, 3, 15))
        assert len(result) == 2

    def test_exact_single_day(self, sample_df):
        result = filter_by_date(sample_df, date(2025, 3, 15), date(2025, 3, 15))
        assert len(result) == 1
        assert result.iloc[0]["description_normalized"] == "Grocery"

    def test_returns_empty_for_out_of_range(self, sample_df):
        result = filter_by_date(sample_df, date(2020, 1, 1), date(2020, 12, 31))
        assert len(result) == 0

    def test_index_is_reset(self, sample_df):
        """Index must be 0-based after filtering so DataGrid row tracking stays correct."""
        result = filter_by_date(sample_df, date(2025, 9, 1), date(2025, 9, 30))
        assert list(result.index) == list(range(len(result)))

    def test_all_rows_returned_when_range_covers_full_dataset(self, sample_df):
        result = filter_by_date(sample_df, date(2025, 1, 1), date(2025, 12, 31))
        assert len(result) == len(sample_df)


# ---------------------------------------------------------------------------
# aggregate_spending
# ---------------------------------------------------------------------------


class TestAggregateSpending:
    def test_excludes_credit_rows(self, sample_df):
        """Rows where debit is NaN should not appear in the aggregation."""
        result = aggregate_spending(sample_df)
        expected_count = int(sample_df["debit"].notna().sum())
        assert int(result["count"].sum()) == expected_count

    def test_groups_by_merchant(self, sample_df):
        result = aggregate_spending(sample_df)
        assert set(result["description_normalized"]) == {"Grocery", "Coffee"}

    def test_totals_are_correct(self, sample_df):
        result = aggregate_spending(sample_df)
        grocery_total = result.loc[result["description_normalized"] == "Grocery", "total"].iloc[0]
        assert grocery_total == pytest.approx(80.0)

    def test_count_per_merchant_is_correct(self, sample_df):
        result = aggregate_spending(sample_df)
        grocery_count = result.loc[result["description_normalized"] == "Grocery", "count"].iloc[0]
        assert grocery_count == 2

    def test_returns_dataframe(self, sample_df):
        result = aggregate_spending(sample_df)
        assert isinstance(result, pd.DataFrame)

    def test_empty_input_returns_empty_dataframe(self):
        empty = pd.DataFrame(columns=["description_normalized", "debit"])
        result = aggregate_spending(empty)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# get_sort_order
# ---------------------------------------------------------------------------


class TestGetSortOrder:
    def test_sorted_descending_by_total(self, sample_df):
        """Merchant with highest total spend should appear first."""
        totals = aggregate_spending(sample_df)
        order = get_sort_order(totals)
        # Grocery (80.0) must rank above Coffee (5.0)
        assert order.index("Grocery") < order.index("Coffee")

    def test_returns_all_merchants(self, sample_df):
        totals = aggregate_spending(sample_df)
        order = get_sort_order(totals)
        assert set(order) == {"Grocery", "Coffee"}

    def test_returns_list(self, sample_df):
        totals = aggregate_spending(sample_df)
        assert isinstance(get_sort_order(totals), list)

    def test_single_merchant_returns_single_item_list(self):
        totals = pd.DataFrame(
            {
                "description_normalized": ["OnlyStore"],
                "total": [99.0],
                "count": [3],
            }
        )
        assert get_sort_order(totals) == ["OnlyStore"]


# ---------------------------------------------------------------------------
# match_preset
# ---------------------------------------------------------------------------


class TestMatchPreset:
    def test_matches_pre_mds(self):
        assert match_preset(date(2025, 1, 1), date(2025, 8, 25)) == "pre_mds"

    def test_matches_mds(self):
        assert match_preset(date(2025, 8, 26), date(2025, 12, 31)) == "mds"

    def test_returns_none_for_custom_range(self):
        assert match_preset(date(2025, 3, 1), date(2025, 6, 30)) is None

    def test_returns_none_when_only_start_matches(self):
        assert match_preset(date(2025, 1, 1), date(2025, 6, 30)) is None

    def test_returns_none_when_only_end_matches(self):
        assert match_preset(date(2025, 3, 1), date(2025, 8, 25)) is None

    def test_accepts_custom_presets_dict(self):
        custom = {"q1": (date(2025, 1, 1), date(2025, 3, 31))}
        assert match_preset(date(2025, 1, 1), date(2025, 3, 31), presets=custom) == "q1"

    def test_custom_presets_no_match_returns_none(self):
        custom = {"q1": (date(2025, 1, 1), date(2025, 3, 31))}
        assert match_preset(date(2025, 4, 1), date(2025, 6, 30), presets=custom) is None


# ---------------------------------------------------------------------------
# DATE_PRESETS sanity checks
# ---------------------------------------------------------------------------


class TestDatePresets:
    def test_all_values_are_date_objects(self):
        for key, (start, end) in DATE_PRESETS.items():
            assert isinstance(start, date), f"{key} start is not a date"
            assert isinstance(end, date), f"{key} end is not a date"

    def test_start_is_before_end_for_all_presets(self):
        for key, (start, end) in DATE_PRESETS.items():
            assert start < end, f"{key}: start ({start}) is not before end ({end})"

    def test_expected_keys_exist(self):
        assert "pre_mds" in DATE_PRESETS
        assert "mds" in DATE_PRESETS


# ---------------------------------------------------------------------------
# get_git_hash
# ---------------------------------------------------------------------------


class TestGetGitHash:
    def test_returns_a_string(self):
        assert isinstance(get_git_hash(), str)

    def test_returns_unknown_when_git_unavailable(self):
        with patch("utils.subprocess.check_output", side_effect=Exception("no git")):
            assert get_git_hash() == "unknown"

    def test_strips_whitespace_from_git_output(self):
        with patch("utils.subprocess.check_output", return_value="abc1234\n"):
            assert get_git_hash() == "abc1234"
