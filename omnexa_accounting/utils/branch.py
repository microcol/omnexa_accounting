# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _


def validate_branch_company(doc):
	"""Ensure selected branch belongs to document company."""
	branch = getattr(doc, "branch", None)
	if not branch:
		return

	branch_company = frappe.db.get_value("Branch", branch, "company")
	if not branch_company:
		frappe.throw(_("Branch {0} does not exist.").format(branch), title=_("Branch"))

	if branch_company != doc.company:
		frappe.throw(_("Branch belongs to a different company."), title=_("Branch"))
