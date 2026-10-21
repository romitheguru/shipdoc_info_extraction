"""uv run python -m unittest discover tests"""
import glob, json, os, unittest
from pathlib import Path

from shipdoc.pages import ROOT, documents
from shipdoc.postprocess import currency, iata, iso_date, normalise, number
from shipdoc.schema import errors


def gold():
    return [json.loads(Path(f).read_text()) for f in sorted(glob.glob(os.path.join(ROOT, "data", "*", "labels", "*.json")))]


class Dates(unittest.TestCase):
    def test_formats_in_train(self):  # note 03: DD-MON-YYYY, MM/DD, Month DD YYYY, DD/MM, ISO
        for raw, iso in [("05-MAR-2024", "2024-03-05"), ("March 5, 2024", "2024-03-05"), ("Sep 30 2024", "2024-09-30"),
                         ("2024-03-05", "2024-03-05"), ("03/25/2024", "2024-03-25"), ("25/03/2024", "2024-03-25")]:
            self.assertEqual(iso_date(raw), (iso, False), raw)

    def test_unseen_variants(self):
        for raw, iso in [("2024/03/05", "2024-03-05"), ("5 March 2024", "2024-03-05"), ("5th March 2024", "2024-03-05"),
                         ("Sept. 5, 2024", "2024-09-05"), ("05.Mar.2024", "2024-03-05"), ("25.03.2024", "2024-03-25"),
                         ("25-03-2024", "2024-03-25")]:
            self.assertEqual(iso_date(raw)[0], iso, raw)

    def test_ambiguous_slash_date_is_flagged(self):
        self.assertEqual(iso_date("03/04/2024"), ("2024-03-04", True))
        self.assertEqual(iso_date("04/04/2024"), ("2024-04-04", False))  # same either way

    def test_unparseable_or_invalid_is_null(self):
        for raw in [None, "", "N/A", "next Tuesday", "13/13/2024", "2024-02-31x"]:
            self.assertEqual(iso_date(raw)[0], None, raw)


class Numbers(unittest.TestCase):
    def test_numbers(self):
        for raw, out in [("1,234.50", "1234.50"), ("USD 1,200", "1200"), ("12 PCS", "12"), ("125.5 KG", "125.5"),
                         ("1.234,50", "1234.50"), ("125,5 kg", "125.5"), ("1,200,000", "1200000"), ("-", None), (None, None)]:
            self.assertEqual(number(raw), out, raw)

    def test_integer_fields_read_dot_thousands(self):
        for raw, out in [("2.500", "2500"), ("1.000.000", "1000000"), ("250", "250"), ("1,000", "1000"), ("2.5", "2.5")]:
            self.assertEqual(number(raw, integer=True), out, raw)
        self.assertEqual(number("2.500"), "2.500")  # amounts keep the decimal reading


class Codes(unittest.TestCase):
    def test_iata(self):
        for raw, out in [("HKG", "HKG"), ("hkg", "HKG"), ("HKG HONG KONG", "HKG"), ("Los Angeles (LAX)", "LAX"),
                         ("LONDON LHR", "LHR"), ("Hong Kong", None), (None, None)]:
            self.assertEqual(iata(raw), out, raw)

    def test_currency(self):
        for raw, out in [("USD", "USD"), ("eur", "EUR"), ("JPY (Yen)", "JPY"), ("€", "EUR"), ("$", None), (None, None)]:
            self.assertEqual(currency(raw), out, raw)


class Verbatim(unittest.TestCase):
    def test_ids_keep_every_character(self):
        doc, _ = normalise({"doc_type": "invoice", "header": {"invoice_number": " GHSR61902O6 "},
                            "line_items": [{"supplier_part_number": "UO/2040XK7", "customer_part_number": "—",
                                            "purchase_order": "PO-0012", "quantity": "1,200"}]})
        self.assertEqual(doc["header"]["invoice_number"], "GHSR61902O6")
        self.assertEqual(doc["line_items"], [{"supplier_part_number": "UO/2040XK7", "customer_part_number": None,
                                              "purchase_order": "PO-0012", "quantity": "1200"}])


class Gold(unittest.TestCase):
    def test_gold_round_trips_unchanged(self):
        for g in gold():
            doc, flags = normalise(g)
            self.assertEqual(doc, {k: g[k] for k in ("doc_type", "header", "line_items")}, g["doc_id"])
            self.assertEqual(flags, {}, g["doc_id"])  # gold dates are ISO, so never ambiguous

    def test_gold_and_sample_pass_schema(self):
        self.assertEqual(errors({g["doc_id"]: {k: g[k] for k in ("doc_type", "header", "line_items")} for g in gold()}), [])
        self.assertEqual(errors(json.loads(Path(ROOT, "sample_submission.json").read_text())), [])

    def test_schema_catches_problems(self):
        bad = {"x": {"doc_type": "invoice", "header": {"carrier": None}, "line_items": []}}
        self.assertTrue(errors(bad))


class Pages(unittest.TestCase):
    def test_test_split_grouping(self):
        docs = documents("test")
        self.assertEqual((len(docs), sum(map(len, docs.values()))), (200, 280))
        multi = next(p for p in docs.values() if len(p) > 1)
        self.assertEqual([os.path.basename(p).split("_p")[1][0] for p in multi], [str(i + 1) for i in range(len(multi))])


if __name__ == "__main__":
    unittest.main()
