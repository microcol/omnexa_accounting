# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PurchaseOrder(Document):
	def validate(self):
		if not self.items:
			frappe.throw(_("Purchase Order requires at least one item."), title=_("Items"))
		total_qty = 0
		total_amount = 0
		for row in self.items:
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: Qty must be greater than zero.").format(row.idx), title=_("Items"))
			if flt(row.rate) < 0:
				frappe.throw(_("Row {0}: Rate cannot be negative.").format(row.idx), title=_("Items"))
			row.amount = flt(row.qty) * flt(row.rate)
			total_qty += flt(row.qty)
			total_amount += flt(row.amount)
		self.total_qty = total_qty
		self.grand_total = total_amount
