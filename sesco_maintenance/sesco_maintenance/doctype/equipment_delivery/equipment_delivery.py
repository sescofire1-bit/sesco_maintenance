import frappe
from frappe import _
from frappe.model.document import Document

from sesco_maintenance.movement import apply_movement, revert_movements, set_receipt_reference, validate_rows


class EquipmentDelivery(Document):
	def validate(self):
		validate_rows(self, allowed_status=("Ready", "Damaged"), customer=self.customer)
		set_receipt_reference(self)
		for row in self.items:
			status = frappe.db.get_value("Customer Equipment", row.equipment, "status")
			row.result = "OK" if status == "Ready" else "Damaged"
		if self.delivery_method != "Company Driver":
			self.driver = None

	def on_submit(self):
		driver = frappe.db.get_value("Employee", self.driver, "employee_name") if self.driver else None
		how = _(self.delivery_method) + (f" — {driver}" if driver else "")
		for row in self.items:
			notes = how + (" — " + _("Damaged, returned free of charge") if row.result == "Damaged" else "")
			apply_movement(
				self,
				row.equipment,
				"Delivered",
				{"status": "At Customer", "current_supplier": None},
				_("At Customer"),
				notes=notes,
			)

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Equipment Activity",)
		revert_movements(self)
