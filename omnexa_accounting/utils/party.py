# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Shared party helpers for AR/AP and experience checkout."""

import re

import frappe
from frappe.utils import cint


WEB_GUEST_CUSTOMER_NAME = "Web Guest"


def get_or_create_web_guest_customer(company: str) -> str:
	"""One synthetic customer per company for anonymous web checkout."""
	name = frappe.db.get_value(
		"Customer",
		{"company": company, "customer_name": WEB_GUEST_CUSTOMER_NAME},
		"name",
	)
	if name:
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"company": company,
			"customer_name": WEB_GUEST_CUSTOMER_NAME,
			"status": "Active",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def get_effective_credit_days(party_doctype: str, party_name: str) -> int:
	"""Days after posting date for default due date: explicit ``credit_days``, else ``Net N`` in ``payment_terms``."""
	if not party_name or party_doctype not in ("Customer", "Supplier"):
		return 0
	row = frappe.db.get_value(
		party_doctype,
		party_name,
		["credit_days", "payment_terms"],
		as_dict=True,
	)
	if not row:
		return 0
	cd = cint(row.credit_days)
	if cd > 0:
		return cd
	terms = row.payment_terms
	if not terms:
		return 0
	m = re.search(r"(?i)net\D*(\d+)", str(terms).strip())
	if m:
		return cint(m.group(1))
	return 0
