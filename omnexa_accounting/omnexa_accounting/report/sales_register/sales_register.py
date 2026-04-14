import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
		{"label": "Sales Invoice", "fieldname": "name", "fieldtype": "Link", "options": "Sales Invoice", "width": 170},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
		{"label": "Branch", "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 140},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
		{"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 110},
		{"label": "Currency", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 90},
		{"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Currency", "width": 130},
		{"label": "Outstanding", "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120},
		{"label": "Base Grand Total", "fieldname": "base_grand_total", "fieldtype": "Currency", "width": 140},
	]

	conditions = ["si.docstatus = 1"]
	params = {}

	if filters.get("company"):
		conditions.append("si.company = %(company)s")
		params["company"] = filters.company

	if filters.get("branch"):
		conditions.append("si.branch = %(branch)s")
		params["branch"] = filters.branch

	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")
		params["customer"] = filters.customer

	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
		params["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
		params["to_date"] = filters.to_date

	data = frappe.db.sql(
		f"""
		SELECT
			si.posting_date,
			si.name,
			si.company,
			si.branch,
			si.customer,
			si.due_date,
			si.currency,
			si.grand_total,
			si.outstanding_amount,
			si.base_grand_total
		FROM `tabSales Invoice` si
		WHERE {" AND ".join(conditions)}
		ORDER BY si.posting_date DESC, si.modified DESC
		""",
		params,
		as_dict=True,
	)

	return columns, data

