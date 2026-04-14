from frappe.model.document import Document
from frappe.utils import flt


class StockEntryItem(Document):
	def validate(self):
		self.amount = flt(self.qty) * flt(self.rate)
