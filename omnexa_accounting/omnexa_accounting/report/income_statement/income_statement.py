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
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."), title=_("Filters"))

	columns = [
		{"label": _("Section"), "fieldname": "section", "fieldtype": "Data", "width": 140},
		{"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "GL Account", "width": 180},
		{"label": _("Account Name"), "fieldname": "account_name", "fieldtype": "Data", "width": 220},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 140},
	]

	income_rows = _rows_for_type(filters, "Income", "Revenue")
	expense_rows = _rows_for_type(filters, "Expense", "Expense")
	net_profit = flt(sum(flt(r.amount) for r in income_rows)) - flt(sum(flt(r.amount) for r in expense_rows))

	data = income_rows + expense_rows + [{"section": _("Net Result"), "account_name": _("Net Profit / Loss"), "amount": net_profit}]
	return columns, data


def _rows_for_type(filters, account_type, section_label):
	conditions = [
		"je.company = %(company)s",
		"je.docstatus = 1",
		"je.posting_date between %(from_date)s and %(to_date)s",
		"ga.account_type = %(account_type)s",
	]
	params = frappe._dict(filters.copy())
	params.account_type = account_type

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
		amount = flt(row.total_credit) - flt(row.total_debit) if account_type == "Income" else flt(row.total_debit) - flt(row.total_credit)
		data.append(
			{
				"section": _(section_label),
				"account": row.account,
				"account_name": row.account_name,
				"amount": amount,
			}
		)
	return data
