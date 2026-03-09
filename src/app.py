import os
from pathlib import Path

import altair as alt
import pandas as pd
from dotenv import load_dotenv
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Load variables from .env when running locally.
# On Posit Connect / shinyapps.io, set these as deployment variables instead.
load_dotenv()

# Google Sheets identifiers — both found in the sheet URL:
# https://docs.google.com/spreadsheets/d/<GSHEET_ID>/edit#gid=<GSHEET_GID>
GSHEET_ID  = os.getenv("GSHEET_ID", "")
GSHEET_GID = os.getenv("GSHEET_GID", "0")  # "0" = first tab

# Local path used during development (relative to this file)
LOCAL_DATA_PATH = Path(__file__).parent.parent / "data" / "processed" / "transactions_2025.csv"

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data() -> tuple[pd.DataFrame, str]:
    """Load transactions CSV from local disk if available, otherwise from Google Sheets.

    Returns the DataFrame and a source tag ("local" or "google_sheets") so the
    UI can display where the data came from.
    """
    if LOCAL_DATA_PATH.exists():
        return pd.read_csv(LOCAL_DATA_PATH, parse_dates=["date"]), "local"

    # Google Sheets CSV export URL — sheet must be shared as "Anyone with the link"
    url = f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/export?format=csv&gid={GSHEET_GID}"
    return pd.read_csv(url, parse_dates=["date"]), "google_sheets"


df, data_source = load_data()

# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

# Small badge shown in the header indicating where the data was loaded from
source_badge = ui.span(
    "Local file" if data_source == "local" else "Google Sheets",
    style=(
        "font-size:0.75rem; padding:2px 8px; border-radius:4px; "
        + ("background:#d4edda; color:#155724;" if data_source == "local"
           else "background:#cce5ff; color:#004085;")
    ),
)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

app_ui = ui.page_sidebar(
    # --- Sidebar (filters live here) ---
    ui.sidebar(
        ui.h5("Filters"),
        # TODO: add filter components here (dropdowns, checkboxes, date range, etc.)
        ui.input_action_button(
            "clear_filters",
            "Clear Filters",
            style="margin-top:auto; width:100%;",
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
    @render_widget
    def spending_chart():
        # Use data_view() so the chart reacts to any active DataGrid filters.
        # Keep raw rows (not aggregated) so each segment = one transaction.
        filtered_df = (
            transactions_table.data_view()
            .loc[lambda d: d["debit"].notna()]
            .sort_values("date")  # consistent stacking order within each bar
        )

        # Separate aggregation for the count label and x-position at bar end
        totals_df = (
            filtered_df
            .groupby("description_normalized", as_index=False)
            .agg(total=("debit", "sum"), count=("debit", "count"))
        )

        # Explicit sort order derived from totals — most reliable in layered charts
        sort_order = totals_df.sort_values("total", ascending=False)["description_normalized"].tolist()

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

    @render.data_frame
    def transactions_table():
        return render.DataGrid(df, filters=True, height="350px")

    @reactive.effect
    @reactive.event(input.clear_filters)
    async def _():
        # Send a message to the JS handler to clear all DataGrid filter inputs
        await session.send_custom_message("clear_datagrid_filters", {"id": "transactions_table"})

    @render.text
    def row_count():
        # data_view() reflects the currently filtered subset of rows
        rows = transactions_table.data_view().shape[0]
        return f"{rows:,} rows"


app = App(app_ui, server)
