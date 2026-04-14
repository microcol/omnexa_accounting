# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe

from omnexa_core.omnexa_core.branch_access import enforce_branch_access, get_allowed_branches
from omnexa_core.omnexa_core.user_context import apply_company_branch_defaults


def enforce_branch_access_for_doc(doc, method=None):
	enforce_branch_access(doc)


def populate_company_branch_from_user_context(doc, method=None):
	apply_company_branch_defaults(doc)


def _get_query_for_table(table: str, user=None):
	user = user or frappe.session.user
	allowed = get_allowed_branches(user)
	if allowed is None:
		return ""
	if not allowed:
		return "1=0"
	quoted = ", ".join([frappe.db.escape(v) for v in allowed])
	return f"(`tab{table}`.branch in ({quoted}) or `tab{table}`.branch is null or `tab{table}`.branch = '')"


def sales_invoice_query_conditions(user=None):
	return _get_query_for_table("Sales Invoice", user)


def purchase_invoice_query_conditions(user=None):
	return _get_query_for_table("Purchase Invoice", user)


def payment_entry_query_conditions(user=None):
	return _get_query_for_table("Payment Entry", user)


def journal_entry_query_conditions(user=None):
	return _get_query_for_table("Journal Entry", user)


def bank_reconciliation_query_conditions(user=None):
	return _get_query_for_table("Bank Reconciliation", user)
