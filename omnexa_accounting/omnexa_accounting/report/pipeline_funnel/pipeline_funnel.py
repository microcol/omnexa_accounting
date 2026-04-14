import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})

	columns = [
		{"label": "Stage", "fieldname": "stage", "fieldtype": "Data", "width": 160},
		{"label": "Opportunities", "fieldname": "opportunity_count", "fieldtype": "Int", "width": 120},
		{"label": "Total Amount", "fieldname": "total_amount", "fieldtype": "Currency", "width": 140},
		{"label": "Weighted Amount", "fieldname": "weighted_amount", "fieldtype": "Currency", "width": 150},
	]

	conditions = ["po.docstatus < 2"]
	params = {}

	if filters.get("company"):
		conditions.append("po.company = %(company)s")
		params["company"] = filters.company

	if filters.get("from_date"):
		conditions.append("po.closing_date >= %(from_date)s")
		params["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("po.closing_date <= %(to_date)s")
		params["to_date"] = filters.to_date

	data = frappe.db.sql(
		f"""
		SELECT
			po.stage,
			COUNT(po.name) AS opportunity_count,
			COALESCE(SUM(po.amount), 0) AS total_amount,
			COALESCE(SUM(po.amount * (po.probability / 100.0)), 0) AS weighted_amount
		FROM `tabPipeline Opportunity` po
		WHERE {" AND ".join(conditions)}
		GROUP BY po.stage
		ORDER BY opportunity_count DESC, total_amount DESC
		""",
		params,
		as_dict=True,
	)

	return columns, data

