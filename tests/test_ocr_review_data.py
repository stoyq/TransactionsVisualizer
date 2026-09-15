from io import BytesIO

import pandas as pd

from ocr_review_data import annotated_image, apply_edits, export_csv, load_summary, table_view


def test_review_export_preserves_source_and_other_rows(tmp_path):
    source = tmp_path / "ocr_image_summary.csv"
    source.write_text(
        "source_image,store_name,receipt_code,amount,date,description\n"
        "a.jpg,原店,00123,9,,\n"
        "b.jpg,另一家,00456,100,2026-08-31,NA\n",
        encoding="utf-8-sig",
    )
    before = source.read_bytes()
    original = load_summary(source)
    edited = apply_edits(
        original, 0, {"store_name": "新店", "description": 'Tea, "large"', "source_image": "bad"}
    )
    payload = export_csv(edited)
    exported = pd.read_csv(BytesIO(payload), dtype=str, keep_default_na=False)
    assert source.read_bytes() == before
    assert original.at[0, "store_name"] == "原店"
    assert exported.at[0, "store_name"] == "新店"
    assert exported.at[0, "description"] == 'Tea, "large"'
    assert exported.at[0, "source_image"] == "a.jpg"
    assert exported.at[0, "receipt_code"] == "00123"
    assert exported.iloc[1].equals(original.iloc[1])
    assert payload.startswith(b"\xef\xbb\xbf")


def test_annotated_filename_and_missing_image(tmp_path):
    annotation = tmp_path / "receipt_ocr_res_img.jpg"
    annotation.touch()
    assert annotated_image(tmp_path, "receipt.jpg") == annotation
    assert annotated_image(tmp_path, "missing.jpg") is None


def test_table_sorts_amount_numerically_without_changing_export_values():
    frame = pd.DataFrame({"amount": ["100", "9", ""], "receipt_code": ["001", "002", "003"]})
    view = table_view(frame)
    assert view.sort_values("amount")["receipt_code"].tolist() == ["002", "001", "003"]
    assert frame["amount"].tolist() == ["100", "9", ""]
    frame.at[0, "amount"] = "unclear"
    assert table_view(frame).at[0, "amount"] == "unclear"
