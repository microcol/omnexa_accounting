# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from omnexa_core.omnexa_core.branch_access import get_allowed_branches


def execute(filters=None):
	filters = frappe._dict(filters or {})
	company = filters.get("company")
	if not company:
		frappe.throw(_("Company filter is required."), title=_("Filters"))

	conditions = ["je.company = %(company)s", "je.docstatus = 1"]
	if filters.get("from_date"):
		conditions.append("je.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("je.posting_date <= %(to_date)s")
	if filters.get("branch"):
		conditions.append("je.branch = %(branch)s")
	allowed = get_allowed_branches(company=company)
	if allowed is not None:
		if not allowed:
			return columns(), []
		filters.allowed_branches = tuple(allowed)
		conditions.append("je.branch in %(allowed_branches)s")

	cols = columns()
	data = frappe.db.sql(
		f"""
		SELECT
			je.posting_date,
			je.name AS voucher,
			je.reference,
			je.branch,
			jea.account,
			jea.party_type,
			jea.party,
			jea.debit,
			jea.credit,
			je.remarks
		FROM `tabJournal Entry` je
		INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
		WHERE {' AND '.join(conditions)}
		ORDER BY je.posting_date, je.name, jea.idx
		""",
		filters,
		as_dict=True,
	)
	return cols, data


def columns():
	return [
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Voucher"), "fieldname": "voucher", "fieldtype": "Link", "options": "Journal Entry", "width": 130},
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Data", "width": 130},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 120},
		{"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "GL Account", "width": 170},
		{"label": _("Party Type"), "fieldname": "party_type", "fieldtype": "Data", "width": 100},
		{"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 130},
		{"label": _("Debit"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
	]
