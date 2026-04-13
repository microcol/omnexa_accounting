# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.utils import flt


def get_exchange_rate(company, from_currency, to_currency, exchange_date):
	"""Return rate such that: amount_in_to = amount_in_from * rate. Same currency → 1.0."""
	if from_currency == to_currency:
		return 1.0
	row = frappe.db.sql(
		"""
		select exchange_rate from `tabCurrency Exchange Rate`
		where company = %s and from_currency = %s and to_currency = %s
		and exchange_date <= %s
		order by exchange_date desc
		limit 1
		""",
		(company, from_currency, to_currency, exchange_date),
		as_dict=True,
	)
	if row:
		return flt(row[0].exchange_rate)
	return None


def apply_multi_currency_to_invoice(doc):
	"""Set conversion_rate (from table if still default) and base_* totals."""
	comp_curr = frappe.db.get_value("Company", doc.company, "default_currency")
	if not doc.currency:
		doc.currency = comp_curr
	if doc.currency == comp_curr:
		doc.conversion_rate = 1.0
	else:
		if flt(doc.conversion_rate) <= 0:
			frappe.throw(_("Conversion rate must be positive."), title=_("Currency"))
		is_default_one = abs(flt(doc.conversion_rate) - 1.0) < 1e-9
		if is_default_one:
			er = get_exchange_rate(doc.company, doc.currency, comp_curr, doc.posting_date)
			if er is not None:
				doc.conversion_rate = er
			else:
				frappe.throw(
					_(
						"Add a Currency Exchange Rate for {0} → {1} on or before {2}, or set Conversion Rate manually."
					).format(doc.currency, comp_curr, doc.posting_date),
					title=_("Currency"),
				)
	doc.base_net_total = flt(doc.net_total) * flt(doc.conversion_rate)
	doc.base_tax_total = flt(doc.tax_total) * flt(doc.conversion_rate)
	doc.base_grand_total = flt(doc.grand_total) * flt(doc.conversion_rate)
