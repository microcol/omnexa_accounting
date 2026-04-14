import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company"):
		frappe.throw(_("Company filter is required."), title=_("Filters"))

	conditions = ["company = %(company)s", "is_stock_item = 1"]
	if filters.get("item"):
		conditions.append("name = %(item)s")

	columns = [
		{"label": _("Item"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 160},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Data", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 220},
		{"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 110},
		{"label": _("Current Stock Qty"), "fieldname": "current_stock_qty", "fieldtype": "Float", "width": 130},
		{"label": _("Last Reconciliation"), "fieldname": "last_stock_reconciliation_date", "fieldtype": "Date", "width": 130},
	]

	data = frappe.db.sql(
		f"""
		SELECT
			name AS item,
			item_code,
			item_name,
			stock_uom,
			current_stock_qty,
			last_stock_reconciliation_date
		FROM `tabItem`
		WHERE {' AND '.join(conditions)}
		ORDER BY item_code, item_name
		""",
		filters,
		as_dict=True,
	)
	return columns, data
