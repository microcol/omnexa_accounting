# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Shared party helpers for AR/AP and experience checkout."""

import frappe


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
