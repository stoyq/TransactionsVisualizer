# Changelog

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
