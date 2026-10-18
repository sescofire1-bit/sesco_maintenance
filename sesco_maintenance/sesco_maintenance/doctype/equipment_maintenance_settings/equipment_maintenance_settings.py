import frappe
from frappe import _
from frappe.model.document import Document


class EquipmentMaintenanceSettings(Document):
	def validate(self):
		if self.maintenance_warehouse:
			company = frappe.db.get_value("Warehouse", self.maintenance_warehouse, "company")
			if company != self.company:
				frappe.throw(_("Warehouse {0} belongs to company {1}.").format(self.maintenance_warehouse, company))
		if self.accessories_expense_account:
			company = frappe.db.get_value("Account", self.accessories_expense_account, "company")
			if company != self.company:
				frappe.throw(_("Account {0} belongs to company {1}.").format(self.accessories_expense_account, company))
