# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.utils import getdate


def assert_posting_date_open(company: str, posting_date):
	"""Block GL posting when a matching fiscal period is frozen (see Fiscal Year spec)."""
	if not company or not posting_date:
		return
	pd = getdate(posting_date)
	rows = frappe.db.sql(
		"""
		SELECT p.frozen
		FROM `tabFiscal Year Period` p
		INNER JOIN `tabFiscal Year` fy ON fy.name = p.parent
		WHERE fy.company = %s
		  AND p.period_start_date <= %s
		  AND p.period_end_date >= %s
		""",
		(company, pd, pd),
		as_dict=True,
	)
	if rows and any(r.get("frozen") for r in rows):
		frappe.throw(_("Posting is blocked: fiscal period is frozen."), title=_("Frozen Period"))
