"""Standalone OCR review app. Run: shiny run src/ocr_review.py --port 8001."""

import os
from datetime import datetime
from pathlib import Path

from shiny import App, reactive, render, ui

from ocr_review_data import (
    EDITABLE_FIELDS,
    annotated_image,
    apply_edits,
    export_csv,
    load_summary,
    table_view,
)

DEFAULT_DIR = (
    Path(__file__).resolve().parent.parent
    / "outputs"
    / "ocr"
    / "Taiwan_2026_Jul_to_Sep_transactions"
)
DATA_DIR = Path(os.environ.get("OCR_REVIEW_DIR", str(DEFAULT_DIR))).resolve()
SOURCE_CSV = DATA_DIR / "ocr_image_summary.csv"
IMAGE_DIR = DATA_DIR / "annotated_images"

app_ui = ui.page_fluid(
    ui.tags.style("""
        body { background: #f5f7fa; color: #192c3c; }
        .review-header { padding: 24px 0 12px; }
        .review-toolbar { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
        .review-toolbar .shiny-input-container { margin-bottom: 0; }
        .image-scroll { overflow: auto; background: #edf1f4; padding: 12px; }
        #annotated img { max-width: 100%; height: auto; }
        .card { margin-top: 16px; }
        .source-name { overflow-wrap: anywhere; }
        .hint { color: #526577; }
        .review-workspace { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
                            gap: 20px; align-items: start; }
        .table-panel { position: sticky; top: 12px; }
        .detail-panel { min-width: 0; }
        @media (max-width: 900px) {
            .review-workspace { grid-template-columns: minmax(0, 1fr); }
            .table-panel { position: static; }
        }
    """),
    ui.div(
        ui.h2("Taiwan transactions · OCR review"),
        ui.p(
            "Compare the annotated image with the extracted fields. Edits are kept in this "
            "session; download a reviewed CSV before closing or refreshing the page.",
            class_="hint",
        ),
        class_="review-header",
    ),
    ui.output_ui("workspace"),
    title="OCR review",
)


def server(input, output, session):
    try:
        original = load_summary(SOURCE_CSV)
    except (OSError, ValueError) as exc:
        message = str(exc)

        @render.ui
        def workspace():
            return ui.div(
                ui.h4("Could not load the OCR dataset"),
                ui.p(message),
                ui.p(f"Expected CSV: {SOURCE_CSV}"),
                ui.p("Set OCR_REVIEW_DIR to a folder containing the CSV and annotated_images."),
                class_="alert alert-warning",
            )

        return

    working = reactive.value(original.copy(deep=True))
    selected = reactive.value(0)
    fields = [field for field in EDITABLE_FIELDS if field in original.columns]

    @render.ui
    def workspace():
        return ui.TagList(
            ui.div(
                ui.download_button("download", "Export reviewed CSV", class_="btn-primary"),
                ui.output_text("edit_status", inline=True),
                class_="review-toolbar",
            ),
            ui.p(f"Source: {DATA_DIR.name} / {SOURCE_CSV.name}", class_="hint"),
            ui.div(
                ui.card(
                    ui.card_header("Transactions"),
                    ui.p(
                        "Click a row to review it. Click column headers to sort, "
                        "or use the filters to find a transaction.",
                        class_="hint",
                    ),
                    ui.output_data_frame("summary_table"),
                    class_="table-panel",
                ),
                ui.div(
                    ui.card(
                        ui.card_header("Annotated image"),
                        ui.output_ui("record_heading"),
                        ui.output_ui("image_message"),
                        ui.div(ui.output_image("annotated", height="auto"), class_="image-scroll"),
                        ui.p("Right-click the image to open it at full size.", class_="hint"),
                    ),
                    ui.card(
                        ui.card_header("Extracted fields"),
                        ui.p("Changes are saved to this session as you type.", class_="hint"),
                        ui.output_ui("editor"),
                        ui.input_action_button("reset_row", "Restore this row from original"),
                    ),
                    class_="detail-panel",
                ),
                class_="review-workspace",
            ),
        )

    def field_id(row, field):
        return f"row_{row}_{field}"

    def capture_edits():
        row = selected.get()
        values = {}
        for field in fields:
            # IDs are unique per row so late browser events cannot edit another row.
            key = field_id(row, field)
            if key in input:
                value = input[key]()
                if value is not None:
                    values[field] = value
        current = working.get()
        updated = apply_edits(current, row, values)
        if not updated.equals(current):
            working.set(updated)
        return updated

    @reactive.effect
    def autosave():
        capture_edits()

    @reactive.effect
    @reactive.event(input.reset_row)
    def reset_row():
        row = selected.get()
        for field in fields:
            ui.update_text_area(field_id(row, field), value=original.at[row, field])

    @render.ui
    def record_heading():
        row = selected.get()
        return ui.h5(
            f"{row + 1} / {len(original)} · {original.at[row, 'source_image']}",
            class_="source-name mt-3",
        )

    @reactive.calc
    def image_path():
        return annotated_image(IMAGE_DIR, original.at[selected.get(), "source_image"])

    @render.ui
    def image_message():
        if image_path() is None:
            return ui.p("Annotated image is missing for this row.", class_="alert alert-warning")
        return None

    @render.image(delete_file=False)
    def annotated():
        path = image_path()
        if path is None:
            return None
        return {"src": str(path), "alt": f"OCR annotations for {path.name}"}

    @render.ui
    def editor():
        row = selected.get()
        # Typing must not rebuild the form and interrupt the user's cursor.
        with reactive.isolate():
            values = working.get().iloc[row]
        return ui.TagList(
            *[
                ui.input_text_area(
                    field_id(row, field),
                    field.replace("_", " ").capitalize()
                    + (" (YYYY-MM-DD)" if field == "date" else ""),
                    value=values[field],
                    rows=2 if field in ("description", "combined_text") else 1,
                    width="100%",
                )
                for field in fields
            ],
            ui.tags.details(
                ui.tags.summary("Original OCR values and confidence"),
                ui.tags.dl(
                    *[
                        ui.TagList(ui.tags.dt(column), ui.tags.dd(original.at[row, column] or "—"))
                        for column in original.columns
                    ]
                ),
            ),
        )

    @render.text
    def edit_status():
        changes = working.get().ne(original)
        rows_changed = int(changes.any(axis=1).sum())
        fields_changed = int(changes.sum().sum())
        return f"{rows_changed} rows edited · {fields_changed} fields changed"

    @render.data_frame
    def summary_table():
        return render.DataGrid(
            table_view(original),
            filters=True,
            editable=False,
            selection_mode="row",
            width="100%",
            height="70vh",
        )

    @reactive.effect
    async def sync_table():
        updated = working.get()
        # Updating data in place preserves the table's sort and filter settings.
        with reactive.isolate():
            await summary_table.update_data(table_view(updated))

    @reactive.effect
    @reactive.event(summary_table.cell_selection)
    def select_table_row():
        rows = summary_table.cell_selection()["rows"]
        if rows:
            # Shiny returns source row indices, including after sorting/filtering.
            capture_edits()
            selected.set(rows[0])

    @render.download(
        filename=lambda: f"ocr_image_summary_reviewed_{datetime.now():%Y%m%d_%H%M%S_%f}.csv",
        media_type="text/csv",
    )
    def download():
        yield export_csv(capture_edits())


app = App(app_ui, server)
