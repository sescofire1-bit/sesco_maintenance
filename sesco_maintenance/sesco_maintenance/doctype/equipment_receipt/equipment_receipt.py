import frappe
from frappe import _
from frappe.model.document import Document

from sesco_maintenance.movement import (
	apply_movement,
	check_not_reserved,
	get_equipment_info,
	hydrotest_updates,
	revert_movements,
	validate_rows,
)


class EquipmentReceipt(Document):
	def validate(self):
		self.set_row_defaults()
		validate_rows(self, allowed_status=("At Customer",), customer=self.customer)
		self.total_qty = len(self.items)

	def set_row_defaults(self):
		for row in self.items:
			if row.equipment:
				info = get_equipment_info(row.equipment)
				if info:
					row.equipment_type = info.equipment_type
					row.route = row.route or info.route
			if row.equipment_type and not row.route:
				row.route = frappe.get_cached_value("Equipment Type", row.equipment_type, "default_route")

	def on_submit(self):
		for row in self.items:
			if not row.equipment:
				eq = frappe.get_doc(
					{
						"doctype": "Customer Equipment",
						"customer": self.customer,
						"equipment_type": row.equipment_type,
						"route": row.route,
						"status": "At Customer",
						"current_location": _("At Customer"),
						**hydrotest_updates(row.equipment_type, row.last_hydrotest_date),
					}
				)
				eq.insert(ignore_permissions=True)
				row.db_set({"equipment": eq.name, "is_new": 1})

			updates = {"status": "In Workshop", "route": row.route, "last_receipt": self.name, "current_supplier": None}
			if row.last_hydrotest_date and not row.is_new:
				updates.update(hydrotest_updates(row.equipment_type, row.last_hydrotest_date))
			apply_movement(self, row.equipment, "Received", updates, _("Workshop"), notes=row.notes)

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Equipment Activity",)
		new_rows = [row for row in self.items if row.is_new and row.equipment]
		for row in new_rows:
			check_not_reserved(row.equipment, self, row.idx)

		revert_movements(self)

		# equipment created by this receipt never existed before it, so it goes away with it
		for row in new_rows:
			frappe.delete_doc("Customer Equipment", row.equipment, ignore_permissions=True, force=True)
			row.db_set("equipment", None)
