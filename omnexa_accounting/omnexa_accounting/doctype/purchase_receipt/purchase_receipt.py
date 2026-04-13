# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PurchaseReceipt(Document):
	def validate(self):
		if not self.items:
			frappe.throw(_("Purchase Receipt requires at least one item."), title=_("Items"))
		total_qty = 0
		total_amount = 0
		order_item_map = {}
		if self.purchase_order:
			po = frappe.get_doc("Purchase Order", self.purchase_order)
			if po.docstatus != 1:
				frappe.throw(_("Linked Purchase Order must be submitted."), title=_("Purchase Order"))
			if po.company != self.company or po.supplier != self.supplier:
				frappe.throw(_("Purchase Receipt must match Purchase Order company and supplier."), title=_("Purchase Order"))
			for row in po.items:
				order_item_map[row.item_code] = flt(row.qty)
		for row in self.items:
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: Qty must be greater than zero.").format(row.idx), title=_("Items"))
			if flt(row.rate) < 0:
				frappe.throw(_("Row {0}: Rate cannot be negative.").format(row.idx), title=_("Items"))
			if self.purchase_order and flt(row.qty) > flt(order_item_map.get(row.item_code, 0)):
				frappe.throw(
					_("Row {0}: Receipt Qty cannot exceed Purchase Order Qty for item {1}.").format(row.idx, row.item_code),
					title=_("Purchase Order"),
				)
			row.amount = flt(row.qty) * flt(row.rate)
			total_qty += flt(row.qty)
			total_amount += flt(row.amount)
		self.total_qty = total_qty
		self.grand_total = total_amount
