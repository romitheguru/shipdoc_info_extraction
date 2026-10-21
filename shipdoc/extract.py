"""From model text to the raw dict `postprocess.normalise` expects.

The invoice prompt asks the model to name each column's role before writing rows, so the column decision
is visible. Rows come keyed by role (prompt v2) or by printed header text (v1); both are read here. Role
repairs (see repair_roles) are applied to every row the same way. Anything that looks inconsistent
becomes a flag rather than a silent fix.
"""
import json, re

ROLES = ["supplier_part_number", "customer_part_number", "purchase_order", "quantity"]
BUYER_WORDS = re.compile(r"\b(your|customer|cust|buyer|client)\b", re.I)


def parse_json(text):
    """First {...} block in the model text, or None."""
    text = re.sub(r"```(?:json)?", "", text or "")
    start = text.find("{")
    if start < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(text[start:])[0]
    except json.JSONDecodeError:
        return None


def _key(s):
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def repair_roles(role_of):
    """Structural fixes to the model's column roles, each returned as a review-flag reason.

    - Every item table carries the seller's part number (true for every gold row). If no column has that
      role but exactly one has the buyer's, the model mislabelled it.
    - A header naming the buyer ("Your", "Customer", ...) is the buyer's part number. If the seller's column
      has such a header and the buyer's column doesn't, the two roles are swapped.
    """
    by_role = {r: h for h, r in role_of.items()}
    sup, cus = by_role.get("supplier_part_number"), by_role.get("customer_part_number")
    if sup is None and cus is not None:
        return {**role_of, cus: "supplier_part_number"}, "repaired: only part column was labelled customer"
    if sup and cus and BUYER_WORDS.search(sup) and not BUYER_WORDS.search(cus):
        return {**role_of, sup: "customer_part_number", cus: "supplier_part_number"}, "repaired: swapped seller/buyer part columns"
    return role_of, None


def assemble_invoice(out):
    """Model output (header, po_for_all_rows, columns, rows) -> ({doc_type, header, line_items}, flags)."""
    flags = {}
    role_of = {}
    for c in out.get("columns") or []:
        if isinstance(c, dict) and c.get("header") is not None:
            role = c.get("role") if c.get("role") in ROLES else "other"
            if role != "other" and role in role_of.values():
                flags["rows"] = f"two columns given role {role}"
                continue  # first column with a role wins
            role_of[_key(c["header"])] = role
    original = dict(role_of)
    role_of, repair = repair_roles(role_of)
    rename = {original[h]: r for h, r in role_of.items() if original[h] != r}  # role-keyed rows follow a repair
    if repair:
        flags["rows"] = repair
    elif "supplier_part_number" not in role_of.values():
        flags["rows"] = "no supplier_part_number column"

    rows = []
    for r in out.get("rows") or []:
        if not isinstance(r, dict):
            continue
        row = dict.fromkeys(ROLES)
        for header, value in r.items():
            role = rename.get(header, header) if header in ROLES else role_of.get(_key(header))
            if role is None:
                flags["rows"] = f"cell under unknown column {header!r}"
            elif role != "other":
                row[role] = value
        rows.append(row)

    po = out.get("po_for_all_rows")
    if po and "purchase_order" not in role_of.values():
        for row in rows:
            row["purchase_order"] = po
    return {"doc_type": "invoice", "header": out.get("header") or {}, "line_items": rows}, flags


def assemble(doc_type, text):
    """(raw dict for normalise, flags). Unparseable output -> empty doc of that type, flagged."""
    out = parse_json(text)
    if not isinstance(out, dict):
        return {"doc_type": doc_type, "header": {}, "line_items": []}, {"doc": "unparseable model output"}
    if doc_type == "invoice":
        return assemble_invoice(out)
    return {"doc_type": "waybill", "header": out.get("header") or {}, "line_items": []}, {}
