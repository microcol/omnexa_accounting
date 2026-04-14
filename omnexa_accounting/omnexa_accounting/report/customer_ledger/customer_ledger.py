# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	return _party_ledger("Customer", filters)


def _party_ledger(party_type, filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company"):
		frappe.throw(_("Company filter is required."), title=_("Filters"))
	conditions = ["je.company = %(company)s", "je.docstatus = 1", "jea.party_type = %(party_type)s"]
	filters.party_type = party_type
	if filters.get("from_date"):
		conditions.append("je.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("je.posting_date <= %(to_date)s")
	if filters.get("party"):
		conditions.append("jea.party = %(party)s")

	columns = [
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 150},
		{"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "GL Account", "width": 170},
		{"label": _("Voucher"), "fieldname": "voucher", "fieldtype": "Link", "options": "Journal Entry", "width": 130},
		{"label": _("Debit"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
		{"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 120},
	]
	rows = frappe.db.sql(
		f"""
		SELECT je.posting_date, jea.party, jea.account, je.name AS voucher, jea.debit, jea.credit
		FROM `tabJournal Entry` je
		INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
		WHERE {' AND '.join(conditions)}
		ORDER BY jea.party, je.posting_date, je.name, jea.idx
		""",
		filters,
		as_dict=True,
	)
	balances = {}
	data = []
	for row in rows:
		key = row.party or ""
		balances[key] = flt(balances.get(key)) + flt(row.debit) - flt(row.credit)
		row.balance = balances[key]
		data.append(row)
	return columns, data
