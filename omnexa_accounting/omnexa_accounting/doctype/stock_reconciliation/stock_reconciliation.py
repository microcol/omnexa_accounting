# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, flt, getdate


class StockReconciliation(Document):
	def validate(self):
		if not self.items:
			frappe.throw(_("Add at least one stock reconciliation item."), title=_("Stock Reconciliation"))
		for row in self.items:
			it = frappe.get_doc("Item", row.item)
			if it.company != self.company:
				frappe.throw(_("Row {0}: Item belongs to a different company.").format(row.idx), title=_("Stock Reconciliation"))
			if not it.is_stock_item:
				frappe.throw(_("Row {0}: Item is not a stock item.").format(row.idx), title=_("Stock Reconciliation"))
			row.item_code = it.item_code
			row.system_qty = flt(it.current_stock_qty)
			row.variance_qty = flt(row.counted_qty) - flt(row.system_qty)
		self.next_reconciliation_date = self._calculate_next_date()

	def on_submit(self):
		for row in self.items:
			frappe.db.set_value(
				"Item",
				row.item,
				{
					"current_stock_qty": flt(row.counted_qty),
					"last_stock_reconciliation_date": self.reconciliation_date,
				},
				update_modified=False,
			)

	def _calculate_next_date(self):
		d = getdate(self.reconciliation_date)
		if self.cadence == "Weekly":
			return add_days(d, 7)
		if self.cadence == "Monthly":
			return add_months(d, 1)
		return add_months(d, 3)
