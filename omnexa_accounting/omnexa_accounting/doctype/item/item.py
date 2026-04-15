# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Item(Document):
	def validate(self):
		self._sync_product_type_logic()
		existing = frappe.db.get_value(
			"Item",
			{"company": self.company, "item_code": self.item_code},
			"name",
		)
		if existing and (not self.name or existing != self.name):
			frappe.throw(_("Item Code must be unique per company."), title=_("Duplicate"))

	def _sync_product_type_logic(self):
		product_type = (self.product_type or "").strip()
		if product_type == "Service":
			self.is_stock_item = 0
			self.is_purchase_item = 0 if self.is_purchase_item is None else self.is_purchase_item
			self.can_be_manufactured = 0
			self.manufacturing_role = "Service"
		elif product_type == "Raw Material":
			self.is_stock_item = 1
			self.is_purchase_item = 1
			self.is_sales_item = 0 if self.is_sales_item is None else self.is_sales_item
			self.can_be_manufactured = 0
			self.manufacturing_role = "Raw Material"
		elif product_type == "Consumable":
			self.is_stock_item = 1
			self.is_purchase_item = 1
			self.can_be_manufactured = 0
			self.manufacturing_role = "Consumable"
		elif product_type == "Kit":
			self.is_stock_item = 0
			self.can_be_manufactured = 1
			if not self.manufacturing_role or self.manufacturing_role == "Finished Good":
				self.manufacturing_role = "Sub Assembly"
		else:
			if not self.manufacturing_role or self.manufacturing_role == "Service":
				self.manufacturing_role = "Finished Good"
