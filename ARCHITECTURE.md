# Architecture

This document explains the structural decisions behind the codebase — not what the code does, but *why* it is organised the way it is.

---

## `utils.py` vs `app.py` — where does logic live?

The codebase draws a hard line between two concerns:

| File | Responsibility |
|---|---|
| `src/utils.py` | Pure data logic — DataFrames in, DataFrames / plain values out |
| `src/app.py` | Presentation logic — data → Altair chart specs + Shiny reactive outputs |

### `utils.py` — framework-agnostic data logic

Everything in `utils.py` is a plain Python function with no dependency on Shiny or Altair. It takes DataFrames (or primitives) as input and returns DataFrames (or primitives) as output. There are no side effects and no UI concerns.

This matters because it makes the logic **unit-testable in isolation**. You can call `filter_by_date()` or `build_daily_heatmap_df()` in a test with a small hand-crafted DataFrame and assert on the result directly, without starting a Shiny server or rendering a chart.

The rule of thumb: if a function can be fully described as "given this data, return that data", it belongs in `utils.py`.

### `app.py` — framework-coupled presentation logic

`app.py` is responsible for turning data into Altair chart specs and Shiny widgets. This code is inherently coupled to the Altair and Shiny APIs — it uses `@render_widget`, `@reactive.calc`, `alt.Chart`, and so on.

There is no meaningful way to unit test this layer in isolation. You cannot usefully assert that `mark_rect(cornerRadius=2)` is correct without rendering the chart, and Shiny's reactive graph only executes inside a running session. That is not a problem — it is expected. The correctness of this layer is validated by running the app and looking at it.

Moving Altair chart construction into `utils.py` would drag a framework dependency into what should be a framework-agnostic module, and would gain nothing testable in return.

### In practice — examples of the split

**Calendar heatmap**

- **`build_daily_heatmap_df()`** lives in `utils.py` — aggregates transactions to daily totals, ranks the top 3 per day, and formats tooltip strings. Pure data logic, 10 unit tests.
- **`calendar_heatmap()`** lives in `app.py` — calls `build_daily_heatmap_df()`, then constructs the Altair `mark_rect` chart spec with axis config, colour scale, and tooltip bindings. Framework-coupled, not unit tested.

**Monthly spending line plot**

- **`build_monthly_spending_df()`** lives in `utils.py` — groups debit transactions by calendar month and returns one row per month with a `total` column. Pure data logic, 7 unit tests.
- **`monthly_spending_chart()`** lives in `app.py` — calls `build_monthly_spending_df()`, then constructs the Altair `mark_line` chart spec. Framework-coupled, not unit tested.

New features should follow the same pattern: extract the data transformation into `utils.py` first, test it there, then wire it into the Shiny/Altair layer in `app.py`.
