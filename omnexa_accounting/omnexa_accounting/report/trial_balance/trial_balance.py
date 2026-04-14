# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.utils import flt

from omnexa_core.omnexa_core.branch_access import get_allowed_branches


def execute(filters=None):
	filters = frappe._dict(filters or {})
	company = filters.get("company")
	if not company:
		frappe.throw(_("Company filter is required."), title=_("Filters"))

	columns = [
		{"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "GL Account", "width": 190},
		{"label": _("Account Name"), "fieldname": "account_name", "fieldtype": "Data", "width": 200},
		{"label": _("Account Type"), "fieldname": "account_type", "fieldtype": "Data", "width": 110},
		{"label": _("Opening Dr"), "fieldname": "opening_debit", "fieldtype": "Currency", "width": 120},
		{"label": _("Opening Cr"), "fieldname": "opening_credit", "fieldtype": "Currency", "width": 120},
		{"label": _("Period Dr"), "fieldname": "period_debit", "fieldtype": "Currency", "width": 120},
		{"label": _("Period Cr"), "fieldname": "period_credit", "fieldtype": "Currency", "width": 120},
		{"label": _("Closing Dr"), "fieldname": "closing_debit", "fieldtype": "Currency", "width": 120},
		{"label": _("Closing Cr"), "fieldname": "closing_credit", "fieldtype": "Currency", "width": 120},
	]

	data = _build_rows(filters)
	return columns, data


def _build_rows(filters):
	conditions = ["je.company = %(company)s", "je.docstatus = 1"]
	allowed = get_allowed_branches(company=filters.company)
	if allowed is not None:
		if not allowed:
			return []
		filters.allowed_branches = tuple(allowed)
		conditions.append("je.branch in %(allowed_branches)s")

	period_condition = "1=1"
	opening_condition = "1=0"
	if filters.get("from_date") and filters.get("to_date"):
		period_condition = "je.posting_date between %(from_date)s and %(to_date)s"
		opening_condition = "je.posting_date < %(from_date)s"
	elif filters.get("to_date"):
		period_condition = "je.posting_date <= %(to_date)s"
		opening_condition = "1=0"

	rows = frappe.db.sql(
		f"""
		SELECT
			jea.account,
			ga.account_name,
			COALESCE(NULLIF(ga.account_type, ''), 'Unclassified') AS account_type,
			SUM(CASE WHEN {opening_condition} THEN jea.debit ELSE 0 END) AS opening_debit,
			SUM(CASE WHEN {opening_condition} THEN jea.credit ELSE 0 END) AS opening_credit,
			SUM(CASE WHEN {period_condition} THEN jea.debit ELSE 0 END) AS period_debit,
			SUM(CASE WHEN {period_condition} THEN jea.credit ELSE 0 END) AS period_credit
		FROM `tabJournal Entry` je
		INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
		INNER JOIN `tabGL Account` ga ON ga.name = jea.account
		WHERE {' AND '.join(conditions)}
		GROUP BY jea.account, ga.account_name, ga.account_type
		ORDER BY ga.account_type, ga.account_number, ga.account_name
		""",
		filters,
		as_dict=True,
	)

	data = []
	for row in rows:
		opening_balance = flt(row.opening_debit) - flt(row.opening_credit)
		period_balance = flt(row.period_debit) - flt(row.period_credit)
		closing_balance = opening_balance + period_balance
		data.append(
			{
				**row,
				"closing_debit": closing_balance if closing_balance > 0 else 0,
				"closing_credit": abs(closing_balance) if closing_balance < 0 else 0,
			}
		)
	return data
