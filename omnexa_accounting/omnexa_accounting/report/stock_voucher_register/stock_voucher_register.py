import frappe
from frappe import _

from omnexa_core.omnexa_core.branch_access import get_allowed_branches


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company"):
		frappe.throw(_("Company filter is required."), title=_("Filters"))

	conditions = ["company = %(company)s"]
	if filters.get("from_date"):
		conditions.append("posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("posting_date <= %(to_date)s")
	if filters.get("purpose"):
		conditions.append("purpose = %(purpose)s")

	allowed = get_allowed_branches(company=filters.company)
	if allowed is not None:
		if not allowed:
			return _columns(), []
		filters.allowed_branches = tuple(allowed)
		conditions.append("branch in %(allowed_branches)s")

	data = frappe.db.sql(
		f"""
		SELECT
			name AS voucher,
			posting_date,
			purpose,
			from_warehouse,
			to_warehouse,
			total_qty,
			branch,
			docstatus
		FROM `tabStock Entry`
		WHERE {' AND '.join(conditions)}
		ORDER BY posting_date DESC, name DESC
		""",
		filters,
		as_dict=True,
	)
	return _columns(), data


def _columns():
	return [
		{"label": _("Voucher"), "fieldname": "voucher", "fieldtype": "Link", "options": "Stock Entry", "width": 140},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Purpose"), "fieldname": "purpose", "fieldtype": "Data", "width": 130},
		{"label": _("From Warehouse"), "fieldname": "from_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 140},
		{"label": _("To Warehouse"), "fieldname": "to_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 140},
		{"label": _("Total Qty"), "fieldname": "total_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 120},
		{"label": _("DocStatus"), "fieldname": "docstatus", "fieldtype": "Int", "width": 80},
	]
