import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from omnexa_accounting.utils.branch import validate_branch_company


class StockEntry(Document):
	def validate(self):
		validate_branch_company(self)
		self._validate_warehouses_company()
		self._validate_rows()
		self._set_totals()

	def on_submit(self):
		self._apply_qty_effect(multiplier=1)

	def on_cancel(self):
		self._apply_qty_effect(multiplier=-1)

	def _validate_warehouses_company(self):
		for wh in [self.from_warehouse, self.to_warehouse]:
			if not wh:
				continue
			wh_company = frappe.db.get_value("Warehouse", wh, "company")
			if wh_company and wh_company != self.company:
				frappe.throw(_("Warehouse belongs to a different company."), title=_("Company"))

	def _validate_rows(self):
		if not self.items:
			frappe.throw(_("At least one stock line is required."), title=_("Stock Entry"))
		for row in self.items:
			if not row.item:
				frappe.throw(_("Row {0}: Item is required.").format(row.idx), title=_("Items"))
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: Qty must be greater than zero.").format(row.idx), title=_("Items"))
			if not row.item_code:
				row.item_code = frappe.db.get_value("Item", row.item, "item_code")
			item_company = frappe.db.get_value("Item", row.item, "company")
			if item_company and item_company != self.company:
				frappe.throw(_("Row {0}: Item belongs to a different company.").format(row.idx), title=_("Items"))
			if not row.uom:
				row.uom = frappe.db.get_value("Item", row.item, "stock_uom")

			source_wh = row.s_warehouse or self.from_warehouse
			target_wh = row.t_warehouse or self.to_warehouse
			if self.purpose == "Material Receipt" and not target_wh:
				frappe.throw(_("Row {0}: Target Warehouse is required for Material Receipt.").format(row.idx), title=_("Warehouse"))
			if self.purpose == "Material Issue" and not source_wh:
				frappe.throw(_("Row {0}: Source Warehouse is required for Material Issue.").format(row.idx), title=_("Warehouse"))
			if self.purpose == "Material Transfer" and (not source_wh or not target_wh):
				frappe.throw(_("Row {0}: Source and Target Warehouse are required for Material Transfer.").format(row.idx), title=_("Warehouse"))

	def _set_totals(self):
		self.total_qty = sum(flt(r.qty) for r in self.items)
		for row in self.items:
			row.amount = flt(row.qty) * flt(row.rate)

	def _apply_qty_effect(self, multiplier=1):
		for row in self.items:
			item_doc = frappe.get_doc("Item", row.item)
			change = 0
			if self.purpose == "Material Receipt":
				change = flt(row.qty)
			elif self.purpose == "Material Issue":
				change = -flt(row.qty)
			elif self.purpose == "Material Transfer":
				change = 0
			item_doc.current_stock_qty = flt(item_doc.current_stock_qty) + (change * multiplier)
			item_doc.save(ignore_permissions=True)
