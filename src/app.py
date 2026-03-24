import os
from pathlib import Path

import altair as alt
from dotenv import load_dotenv
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget

from utils import (
    DATE_PRESETS,
    aggregate_spending,
    build_daily_heatmap_df,
    filter_by_date,
    get_git_hash,
    get_sort_order,
    load_data,
    match_preset,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Load variables from .env when running locally.
# On Posit Connect / shinyapps.io, set these as deployment variables instead.
load_dotenv()

# Google Sheets identifiers — both found in the sheet URL:
# https://docs.google.com/spreadsheets/d/<GSHEET_ID>/edit#gid=<GSHEET_GID>
GSHEET_ID = os.getenv("GSHEET_ID", "")
GSHEET_GID = os.getenv("GSHEET_GID", "0")  # "0" = first tab

# Local path used during development (relative to this file)
LOCAL_DATA_PATH = Path(__file__).parent.parent / "data" / "processed" / "transactions_2025.csv"

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

df, data_source = load_data(LOCAL_DATA_PATH, GSHEET_ID, GSHEET_GID)

# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

# Small badge shown in the header indicating where the data was loaded from
source_badge = ui.span(
    "Local file" if data_source == "local" else "Google Sheets",
    style=(
        "font-size:0.75rem; padding:2px 8px; border-radius:4px; "
        + (
            "background:#d4edda; color:#155724;"
            if data_source == "local"
            else "background:#cce5ff; color:#004085;"
        )
    ),
)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

app_ui = ui.page_sidebar(
    # --- Sidebar (filters live here) ---
    ui.sidebar(
        ui.h5("Filters"),
        ui.input_date_range(
            "date_range",
            "Date range",
            start=df["date"].min().date(),
            end=df["date"].max().date(),
        ),
        ui.input_radio_buttons(
            "date_preset",
            "Date preset",
            choices={"pre_mds": "Pre-MDS", "mds": "MDS", "custom": "Custom"},
            selected="custom",
            inline=True,
        ),
        ui.input_action_button(
            "clear_filters",
            "Clear Filters",
            style="margin-top:auto; width:100%;",
        ),
        ui.div(
            f"version {get_git_hash()}",
            style="font-size:0.7rem; color:#aaa; text-align:center; padding-top:8px;",
        ),
        width=280,
    ),
    # JS handler: clears all React-controlled filter inputs inside the DataGrid.
    # React ignores plain .value assignments, so we use the native HTMLInputElement
    # setter to trigger React's synthetic onChange event.
    ui.tags.script("""
        Shiny.addCustomMessageHandler("clear_datagrid_filters", function(msg) {
            var container = document.getElementById(msg.id);
            if (!container) return;
            var inputs = container.querySelectorAll("input");
            var nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, "value"
            ).set;
            inputs.forEach(function(input) {
                nativeSetter.call(input, "");
                input.dispatchEvent(new Event("input", { bubbles: true }));
            });
        });
    """),
    # Reduce font size for all DataGrid cells
    ui.tags.style("""
        #transactions_table,
        #transactions_table table,
        #transactions_table td,
        #transactions_table th { font-size: 0.72rem; }
    """),
    # --- Main panel: top half (chart) ---
    ui.card(
        ui.card_header("Spending by Merchant"),
        output_widget("spending_chart"),
    ),
    # --- Main panel: middle (calendar heatmap) ---
    ui.card(
        ui.card_header("Daily Spending"),
        output_widget("calendar_heatmap"),
    ),
    # --- Main panel: bottom half (table) ---
    ui.card(
        # Header row: title on the left, data-source badge + row count on the right
        ui.card_header(
            ui.layout_columns(
                ui.span("Transactions"),
                ui.div(
                    source_badge,
                    ui.output_text("row_count"),
                    style="display:flex; align-items:center; gap:12px; justify-content:flex-end;",
                ),
                col_widths=[6, 6],
            )
        ),
        # Transactions table (column filters built in via DataGrid)
        ui.output_data_frame("transactions_table"),
    ),
    title="Transactions Visualizer",
    fillable=True,
)

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------


def server(input, output, session):
    @reactive.calc
    def _date_filtered():
        # Single source of truth for the date-range filter. Returns a DataFrame
        # with a clean 0-based index so DataGrid's positional row tracking is
        # always consistent with the data it was given.
        start, end = input.date_range()
        return filter_by_date(df, start, end)

    def _safe_data_view():
        # data_view() applies the DataGrid's active column filters on top of
        # whatever DataFrame was last passed to it. When the date range changes,
        # there is a one-cycle race where the new (smaller) DataFrame has been
        # set but the old column-filter row indices are still cached — calling
        # data_view() then raises an IndexError. We fall back to _date_filtered()
        # for that one cycle; the stale indices are cleared shortly after by the
        # clear_datagrid_filters JS message.
        try:
            return transactions_table.data_view()
        except IndexError:
            return _date_filtered()

    @render_widget
    def spending_chart():
        # Use _safe_data_view() so the chart reacts to any active DataGrid filters.
        # Keep raw rows (not aggregated) so each segment = one transaction.
        filtered_df = (
            _safe_data_view()
            .loc[lambda d: d["debit"].notna()]
            .sort_values("date")  # consistent stacking order within each bar
        )

        # Separate aggregation for the count label and x-position at bar end
        totals_df = aggregate_spending(filtered_df)

        # Explicit sort order derived from totals — most reliable in layered charts
        sort_order = get_sort_order(totals_df)

        # Stacked bars — white stroke separates individual transaction segments.
        # axis=orient("top") moves the x-axis labels and ticks to the top of the chart.
        # Altair only allows one axis definition per encoding per layer, so the bottom
        # axis is handled separately in the `bottom_axis` layer below.
        bars = (
            alt.Chart(filtered_df)
            .mark_bar(stroke="white", strokeWidth=0.5)
            .encode(
                x=alt.X("sum(debit):Q", title="Total Spent ($)", axis=alt.Axis(orient="top")),
                y=alt.Y("description_normalized:N", sort=sort_order, title=None),
                order=alt.Order("date:T"),
                tooltip=[
                    alt.Tooltip("description_normalized:N", title="Merchant"),
                    alt.Tooltip("debit:Q", title="Amount ($)", format=",.2f"),
                    alt.Tooltip("date:T", title="Date", format="%Y-%m-%d"),
                ],
            )
        )

        # Count label (e.g. "n=5") placed just after the end of each bar.
        # title=None suppresses Altair's default behaviour of using the field name
        # ("total") as an axis title, which would otherwise overlap the bottom axis.
        labels = (
            alt.Chart(totals_df)
            .transform_calculate(label="'n=' + datum.count")
            .mark_text(align="left", dx=4, fontSize=10, color="gray")
            .encode(
                x=alt.X("total:Q", title=None),
                y=alt.Y("description_normalized:N", sort=sort_order),
                text=alt.Text("label:N"),
            )
        )

        # Invisible layer whose sole purpose is to render a second x-axis at the
        # bottom. This is the workaround for Altair's one-axis-per-layer limitation:
        # each layer can only carry one axis definition for a given encoding, so a
        # dedicated invisible layer is used to declare the bottom axis independently.
        bottom_axis = (
            alt.Chart(totals_df)
            .mark_point(opacity=0)
            .encode(
                x=alt.X("total:Q", axis=alt.Axis(orient="bottom", title="Total Spent ($)")),
            )
        )

        return (bars + labels + bottom_axis).properties(height=alt.Step(22))

    @render_widget
    def calendar_heatmap():
        import pandas as pd

        filtered_df = _safe_data_view().loc[lambda d: d["debit"].notna()]

        if filtered_df.empty:
            return alt.Chart(
                pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "total": []})
            ).mark_rect()

        # One row per day — daily total plus the top 3 transactions as
        # pre-formatted strings so Altair can surface them in the tooltip.
        daily_df = build_daily_heatmap_df(filtered_df)

        return (
            alt.Chart(daily_df)
            .mark_rect(cornerRadius=2)
            .encode(
                # yearweek() bins dates into ISO weeks; the labelExpr shows a month
                # name only at the week that crosses into a new month — same trick
                # GitHub uses for its contribution heatmap.
                x=alt.X(
                    "yearweek(date):O",
                    title=None,
                    axis=alt.Axis(
                        labelExpr=(
                            "month(datum.value) != month(datum.value - 7*24*60*60*1000)"
                            " ? timeFormat(datum.value, '%b') : ''"
                        ),
                        ticks=False,
                        domain=False,
                        labelAngle=0,
                    ),
                ),
                # day() uses JavaScript convention: 0=Sun, 1=Mon, …, 6=Sat
                y=alt.Y(
                    "day(date):O",
                    title=None,
                    axis=alt.Axis(
                        labelExpr="['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][datum.value]",
                        ticks=False,
                        domain=False,
                    ),
                ),
                color=alt.Color(
                    "total:Q",
                    scale=alt.Scale(scheme="greens"),
                    title="Spent ($)",
                ),
                tooltip=[
                    alt.Tooltip("date:T", title="Date", format="%b %d, %Y"),
                    alt.Tooltip("total:Q", title="Total ($)", format=",.2f"),
                    alt.Tooltip("top_label:N", title="Top 3"),
                    alt.Tooltip("top_1:N", title="#1"),
                    alt.Tooltip("top_2:N", title="#2"),
                    alt.Tooltip("top_3:N", title="#3"),
                ],
            )
            .properties(height=alt.Step(15), width=alt.Step(15))
        )

    @render.data_frame
    def transactions_table():
        return render.DataGrid(_date_filtered(), filters=True, height="350px", width="100%")

    @reactive.effect
    @reactive.event(input.date_preset)
    def _apply_preset():
        preset = input.date_preset()
        if preset in DATE_PRESETS:
            start, end = DATE_PRESETS[preset]
            ui.update_date_range("date_range", start=start, end=end)

    @reactive.effect
    @reactive.event(input.date_range)
    async def _reset_datagrid_on_date_change():
        # When the date range changes, the DataGrid receives a new (smaller)
        # DataFrame. Its internal column-filter row indices were computed against
        # the previous DataFrame and are now stale — applying them to the new
        # DataFrame causes an out-of-bounds IndexError. Clearing the column
        # filters resets that state so data_view() is always safe to call.
        await session.send_custom_message("clear_datagrid_filters", {"id": "transactions_table"})

    @reactive.effect
    @reactive.event(input.date_range)
    def _sync_preset_radio():
        # When the user edits the date range manually, check if it still matches
        # a preset. If it does, keep the radio on that preset; otherwise switch to
        # "Custom" so the radio always reflects what the picker shows.
        start, end = input.date_range()
        if match_preset(start, end) is None:
            ui.update_radio_buttons("date_preset", selected="custom")

    @reactive.effect
    @reactive.event(input.clear_filters)
    async def _():
        # Reset preset radio and date range picker back to defaults
        ui.update_radio_buttons("date_preset", selected="custom")
        ui.update_date_range(
            "date_range",
            start=df["date"].min().date(),
            end=df["date"].max().date(),
        )
        # Send a message to the JS handler to clear all DataGrid filter inputs
        await session.send_custom_message("clear_datagrid_filters", {"id": "transactions_table"})

    @render.text
    def row_count():
        rows = _safe_data_view().shape[0]
        return f"{rows:,} rows"


app = App(app_ui, server)
