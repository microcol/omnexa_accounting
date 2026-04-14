# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.utils import flt

from omnexa_core.omnexa_core.branch_access import get_allowed_branches


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company"):
		frappe.throw(_("Company filter is required."), title=_("Filters"))

	columns = [
		{"label": _("Section"), "fieldname": "section", "fieldtype": "Data", "width": 140},
		{"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "GL Account", "width": 180},
		{"label": _("Account Name"), "fieldname": "account_name", "fieldtype": "Data", "width": 220},
		{"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 140},
	]

	assets = _rows_for_type(filters, "Asset", "Assets")
	liabilities = _rows_for_type(filters, "Liability", "Liabilities")
	equity = _rows_for_type(filters, "Equity", "Equity")

	data = assets + liabilities + equity
	return columns, data


def _rows_for_type(filters, account_type, section_label):
	conditions = ["je.company = %(company)s", "je.docstatus = 1", "ga.account_type = %(account_type)s"]
	params = frappe._dict(filters.copy())
	params.account_type = account_type

	if filters.get("to_date"):
		conditions.append("je.posting_date <= %(to_date)s")

	allowed = get_allowed_branches(company=filters.company)
	if allowed is not None:
		if not allowed:
			return []
		params.allowed_branches = tuple(allowed)
		conditions.append("je.branch in %(allowed_branches)s")

	rows = frappe.db.sql(
		f"""
		SELECT
			jea.account,
			ga.account_name,
			SUM(jea.debit) AS total_debit,
			SUM(jea.credit) AS total_credit
		FROM `tabJournal Entry` je
		INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
		INNER JOIN `tabGL Account` ga ON ga.name = jea.account
		WHERE {' AND '.join(conditions)}
		GROUP BY jea.account, ga.account_name
		ORDER BY ga.account_number, ga.account_name
		""",
		params,
		as_dict=True,
	)

	data = []
	for row in rows:
		if account_type == "Asset":
			balance = flt(row.total_debit) - flt(row.total_credit)
		else:
			balance = flt(row.total_credit) - flt(row.total_debit)
		data.append(
			{
				"section": _(section_label),
				"account": row.account,
				"account_name": row.account_name,
				"balance": balance,
			}
		)
	return data
