"""uv run python -m unittest discover tests"""
import json, unittest

from shipdoc.extract import assemble, parse_json


def invoice(columns, rows, po=None):
    return json.dumps({"header": {"invoice_number": "INV-1"}, "po_for_all_rows": po,
                       "columns": [{"header": h, "role": r} for h, r in columns], "rows": rows})


class Parse(unittest.TestCase):
    def test_fenced_and_trailing_text(self):
        self.assertEqual(parse_json('```json\n{"a": 1}\n```\nDone.'), {"a": 1})
        self.assertIsNone(parse_json("no json here"))


class Columns(unittest.TestCase):
    def test_roles_map_cells_by_header(self):
        # dev_0037's shape: PO values that look like part numbers stay in purchase_order
        doc, flags = assemble("invoice", invoice(
            [("Line No.", "other"), ("PO No.", "purchase_order"), ("Mfr Part #", "supplier_part_number"),
             ("Quantity", "quantity")],
            [{"PO No.": "B61582571-005", "Mfr Part #": "IPLK87655ZYF", "Quantity": "250"}]))
        self.assertEqual(doc["line_items"], [{"supplier_part_number": "IPLK87655ZYF", "customer_part_number": None,
                                              "purchase_order": "B61582571-005", "quantity": "250"}])
        self.assertEqual(flags, {})

    def test_header_matching_ignores_case_and_spacing(self):
        doc, _ = assemble("invoice", invoice([("Part  No.", "supplier_part_number")], [{"part no.": "X-1"}]))
        self.assertEqual(doc["line_items"][0]["supplier_part_number"], "X-1")

    def test_duplicate_role_and_missing_supplier_column_are_flagged(self):
        _, flags = assemble("invoice", invoice([("A", "quantity"), ("B", "quantity")], []))
        self.assertIn("rows", flags)

    def test_unknown_cell_is_flagged_not_used(self):
        doc, flags = assemble("invoice", invoice([("Part", "supplier_part_number")], [{"Part": "P1", "Mystery": "9"}]))
        self.assertEqual(doc["line_items"][0], {"supplier_part_number": "P1", "customer_part_number": None,
                                                "purchase_order": None, "quantity": None})
        self.assertIn("rows", flags)

    def test_invoice_level_po_only_without_po_column(self):
        cols = [("Part", "supplier_part_number")]
        doc, _ = assemble("invoice", invoice(cols, [{"Part": "P1"}, {"Part": "P2"}], po="PO-9"))
        self.assertEqual([r["purchase_order"] for r in doc["line_items"]], ["PO-9", "PO-9"])
        doc, _ = assemble("invoice", invoice(cols + [("PO", "purchase_order")], [{"Part": "P1", "PO": "A"}], po="PO-9"))
        self.assertEqual(doc["line_items"][0]["purchase_order"], "A")


class HFNames(unittest.TestCase):
    def test_mlx_repo_maps_to_original_weights(self):
        from shipdoc.backends import hf_name
        self.assertEqual(hf_name("mlx-community/Qwen3-VL-8B-Instruct-8bit"), "Qwen/Qwen3-VL-8B-Instruct")
        self.assertEqual(hf_name("mlx-community/Qwen3-VL-4B-Instruct-4bit"), "Qwen/Qwen3-VL-4B-Instruct")
        self.assertEqual(hf_name("Qwen/Qwen3-VL-2B-Instruct"), "Qwen/Qwen3-VL-2B-Instruct")


class Repairs(unittest.TestCase):
    def test_lone_customer_column_becomes_supplier(self):
        doc, flags = assemble("invoice", invoice([("Mfr Part #", "customer_part_number"), ("Qty", "quantity")],
                                                 [{"Mfr Part #": "PX/8685/X96", "Qty": "4,702"}]))
        self.assertEqual(doc["line_items"][0]["supplier_part_number"], "PX/8685/X96")
        self.assertIsNone(doc["line_items"][0]["customer_part_number"])
        self.assertTrue(flags["rows"].startswith("repaired"))

    def test_buyer_worded_supplier_column_is_swapped(self):
        doc, flags = assemble("invoice", invoice([("Part No.", "customer_part_number"), ("Your Part No.", "supplier_part_number")],
                                                 [{"Part No.": "BQN-380-TB3", "Your Part No.": "CP-206286"}]))
        r = doc["line_items"][0]
        self.assertEqual((r["supplier_part_number"], r["customer_part_number"]), ("BQN-380-TB3", "CP-206286"))
        self.assertIn("rows", flags)

    def test_consistent_roles_untouched(self):
        _, flags = assemble("invoice", invoice([("Our Part No.", "supplier_part_number"), ("Your Part No.", "customer_part_number")], []))
        self.assertEqual(flags, {})


class RoleKeyedRows(unittest.TestCase):  # prompt v2
    def test_role_keys_used_directly_and_follow_repairs(self):
        doc, flags = assemble("invoice", invoice([("Mfr Part #", "customer_part_number"), ("Qty", "quantity")],
                                                 [{"supplier_part_number": None, "customer_part_number": "PX/1", "quantity": "5"}]))
        self.assertEqual(doc["line_items"][0], {"supplier_part_number": "PX/1", "customer_part_number": None,
                                                "purchase_order": None, "quantity": "5"})
        self.assertTrue(flags["rows"].startswith("repaired"))

    def test_swap_repair_on_role_keyed_rows(self):
        doc, _ = assemble("invoice", invoice([("Part No.", "customer_part_number"), ("Your Part No.", "supplier_part_number")],
                                             [{"supplier_part_number": "CP-1", "customer_part_number": "BQN-1"}]))
        r = doc["line_items"][0]
        self.assertEqual((r["supplier_part_number"], r["customer_part_number"]), ("BQN-1", "CP-1"))


class Fallbacks(unittest.TestCase):
    def test_unparseable_output_is_flagged(self):
        doc, flags = assemble("waybill", "sorry")
        self.assertEqual((doc["doc_type"], doc["line_items"], flags), ("waybill", [], {"doc": "unparseable model output"}))


if __name__ == "__main__":
    unittest.main()
