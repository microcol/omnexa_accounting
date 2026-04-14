import frappe
from frappe import _
from frappe.utils import flt

from omnexa_core.omnexa_core.branch_access import get_allowed_branches


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company"):
		frappe.throw(_("Company filter is required."), title=_("Filters"))

	conditions = ["se.company = %(company)s", "se.docstatus = 1"]
	if filters.get("from_date"):
		conditions.append("se.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("se.posting_date <= %(to_date)s")
	if filters.get("item"):
		conditions.append("sei.item = %(item)s")

	allowed = get_allowed_branches(company=filters.company)
	if allowed is not None:
		if not allowed:
			return _columns(), []
		filters.allowed_branches = tuple(allowed)
		conditions.append("se.branch in %(allowed_branches)s")

	rows = frappe.db.sql(
		f"""
		SELECT
			se.posting_date,
			se.name AS voucher,
			se.purpose,
			se.branch,
			sei.item,
			sei.item_code,
			sei.s_warehouse,
			sei.t_warehouse,
			sei.qty
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Item` sei ON sei.parent = se.name
		WHERE {' AND '.join(conditions)}
		ORDER BY se.posting_date, se.name, sei.idx
		""",
		filters,
		as_dict=True,
	)

	data = []
	for row in rows:
		in_qty = 0
		out_qty = 0
		if row.purpose == "Material Receipt":
			in_qty = flt(row.qty)
		elif row.purpose == "Material Issue":
			out_qty = flt(row.qty)
		data.append({**row, "in_qty": in_qty, "out_qty": out_qty, "net_qty": in_qty - out_qty})

	return _columns(), data


def _columns():
	return [
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Voucher"), "fieldname": "voucher", "fieldtype": "Link", "options": "Stock Entry", "width": 130},
		{"label": _("Purpose"), "fieldname": "purpose", "fieldtype": "Data", "width": 130},
		{"label": _("Item"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Data", "width": 120},
		{"label": _("Source Warehouse"), "fieldname": "s_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 140},
		{"label": _("Target Warehouse"), "fieldname": "t_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 140},
		{"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Net Qty"), "fieldname": "net_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 120},
	]
