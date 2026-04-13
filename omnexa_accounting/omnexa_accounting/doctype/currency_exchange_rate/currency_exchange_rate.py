# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CurrencyExchangeRate(Document):
	def validate(self):
		if self.from_currency == self.to_currency:
			frappe.throw(_("From and To currency must be different."), title=_("Currency"))
		if flt(self.exchange_rate) <= 0:
			frappe.throw(_("Exchange rate must be positive."), title=_("Currency"))
		existing = frappe.db.get_value(
			"Currency Exchange Rate",
			{
				"company": self.company,
				"exchange_date": self.exchange_date,
				"from_currency": self.from_currency,
				"to_currency": self.to_currency,
			},
			"name",
		)
		if existing and existing != self.name:
			frappe.throw(
				_("An exchange rate for this company, date, and currency pair already exists."),
				title=_("Duplicate"),
			)
