# Changelog

## [Unreleased] - 2026-04-04

### Added

- Monthly spending line plot ("Monthly Spending" card) showing total debit spend per calendar month with point markers; tooltip shows month name and formatted total
- `build_monthly_spending_df()` in `utils.py` — aggregates debit transactions to one row per calendar month (month timestamp + total)
- Center section of the main panel is now split 50/50 into two side-by-side cards: "Daily Spending" (calendar heatmap) on the left and "Monthly Spending" (line plot) on the right

## [Unreleased] - 2026-03-24

### Added

- Calendar heatmap ("Daily Spending" card) showing total spend per day in a GitHub-style grid: weeks on x, days of week on y, green colour scale; x-axis shows month labels only at week boundaries
- Heatmap tooltip shows the daily total plus the top 3 transactions of that day (merchant + amount), with a `"Top 3 (of N transactions)"` header that reflects the actual transaction count for the day
- `build_daily_heatmap_df()` in `utils.py` — extracts the per-day aggregation logic (daily total, top-3 ranking, label formatting) so it can be tested independently
- 10 new unit tests for `build_daily_heatmap_df` in `tests/test_utils.py`

### Updated

- `app.py` now calls `build_daily_heatmap_df()` from `utils.py` instead of defining the aggregation inline

### Docs

- Added `ARCHITECTURE.md` documenting the `utils.py` vs `app.py` split: `utils.py` holds framework-agnostic data logic (testable in isolation), `app.py` holds Shiny/Altair presentation logic (verified by running the app)

## [Unreleased] - 2026-03-22

As the app grows and new features are added, it's important to keep the codebase maintainable and reliable. This release establishes the engineering foundation for that: modular code where each piece can be tested in isolation, automated checks that catch regressions before they reach production, and reproducible builds so the app behaves the same everywhere it runs.

### Added

- `src/utils.py` module extracting all pure logic from `app.py` (`load_data`, `filter_by_date`, `aggregate_spending`, `get_sort_order`, `match_preset`, `DATE_PRESETS`) — new features will be built and tested as standalone modules before being integrated into the main app
- `tests/test_utils.py` with 31 pytest unit tests covering all functions in `utils.py`
- `pyproject.toml` with pytest config (`pythonpath`, `testpaths`) and ruff config (lint + format rules)
- `requirements.lock` pinning exact dependency versions for reproducible CI builds
- `.github/workflows/ci.yml` — GitHub Actions CI pipeline that runs ruff lint, ruff format check, and pytest on every push and pull request to `main`
- CI status badge in `README.md`
- `pytest` and `ruff` added to `src/requirements.txt`

### Updated

- `app.py` now imports from `utils.py`; Shiny UI and reactive logic remain in `app.py`
- CI installs from `requirements.lock` instead of `src/requirements.txt` for reproducibility

## [0.1.1] - 2026-03-09

### Added

- Date range filter in sidebar with "Pre-MDS" (2025-01-01 – 2025-08-25) and "MDS" (2025-08-26 – 2025-12-31) radio button presets; radio auto-switches to "Custom" when dates are edited manually
- "Clear Filters" now also resets the date range and preset radio back to defaults
- X-axis labels and ticks shown at both top and bottom of the spending chart

### Fixed

- `IndexError` when switching date presets: introduced `_date_filtered()` reactive calc (with reset index) as a single source of truth for date filtering, and `_safe_data_view()` guard that catches stale DataGrid row indices during the async clear round-trip

### Updated

- Switched remote data source from Google Drive (via `gdown`) to Google Sheets (direct CSV export URL)
- Replaced `GDRIVE_FILE_ID` env variable with `GSHEET_ID` and `GSHEET_GID`
- Removed `gdown` dependency from `requirements.txt` and `environment.yml`

## [0.1.0] - 2026-03-08

### Added

- Initial Shiny for Python app with sidebar layout and transactions table
- Stacked horizontal bar chart (Altair) grouped by merchant, sorted by total spend, reactive to table filters
- Google Drive fallback for data loading when running on deployment (Posit Connect)
- Environment variable support via `.env` / `python-dotenv` for secure config
- "Clear Filters" button to reset all table column filters
- `environment.yml` and `src/requirements.txt` for local and Posit deployment setup
- Deployed to Posit Connect

![App snapshot](images/snapshots/2026-03-08.png)
