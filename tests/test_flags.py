"""uv run python -m unittest discover tests"""
import json, os, tempfile, unittest

from eval.flags import units
from shipdoc.flags import not_in_ocr, ocr_text


def invoice(rows, **header):
    h = dict.fromkeys(["invoice_number", "invoice_date", "supplier_name", "buyer_name", "ship_to_name", "currency",
                       "total_amount", "awb_number"])
    h.update(header)
    return {"doc_type": "invoice", "header": h, "line_items": [
        {"supplier_part_number": s, "customer_part_number": None, "purchase_order": None, "quantity": q} for s, q in rows]}


class Verifier(unittest.TestCase):
    def test_ocr_text_reads_cache_and_needs_every_page(self):
        with tempfile.TemporaryDirectory() as d:
            json.dump({"texts": ["Part", "GHSR 61902O6"]}, open(os.path.join(d, "x_p1.json"), "w"))
            self.assertEqual(ocr_text(["/img/x_p1.png"], d), "PARTGHSR61902O6")
            self.assertIsNone(ocr_text(["/img/x_p1.png", "/img/x_p2.png"], d))

    def test_flags_ids_missing_from_ocr_ignoring_case_and_space(self):
        doc = invoice([("GHSR61902O6", "5"), ("ghsr 61902o6", "5"), ("GHSR6190206", "5"), ("AB1", "5")], invoice_number="INV-77")
        flags = not_in_ocr(doc, "INV-77PARTGHSR61902O6")
        self.assertEqual(flags, {"row.2.supplier_part_number": "not_in_ocr"})  # 'AB1' is too short to check
        self.assertEqual(not_in_ocr(doc, None), {})


class Units(unittest.TestCase):
    def test_row_and_doc_flags_reach_every_row(self):
        gold = invoice([("P1", "5"), ("P2", "5")])
        pred = invoice([("P1", "5"), ("PX", "5")])
        u = {name: (wrong, reasons) for name, wrong, reasons in units(pred, gold, {"rows": "no supplier_part_number column"})}
        self.assertEqual(u["row.0"], (False, ["no supplier_part_number column"]))
        self.assertEqual(u["row.1"], (True, ["no supplier_part_number column"]))
        self.assertEqual(u["header.invoice_number"], (False, []))


if __name__ == "__main__":
    unittest.main()
