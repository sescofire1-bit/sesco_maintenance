import frappe
from frappe import _
from frappe.model.document import Document


class EquipmentType(Document):
	def validate(self):
		for fieldname in ("service_item", "supplier_service_item"):
			item = self.get(fieldname)
			if item and frappe.db.get_value("Item", item, "is_stock_item"):
				frappe.throw(
					_("{0} must be a non-stock service item: {1} is a stock item.").format(
						_(self.meta.get_label(fieldname)), item
					)
				)
		if self.hydrotest_interval_years and self.hydrotest_interval_years < 0:
			frappe.throw(_("Hydrostatic test interval can't be negative."))
