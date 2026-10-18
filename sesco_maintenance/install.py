import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ROLES = ("Maintenance Storekeeper", "Maintenance Supervisor", "Maintenance Approver")


def after_install():
	setup()


def after_migrate():
	setup()


def setup():
	make_roles()
	make_custom_fields()


def make_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def billing_fields():
	return [
		{
			"fieldname": "maintenance_source_doctype",
			"label": "Maintenance Source Type",
			"fieldtype": "Link",
			"options": "DocType",
			"insert_after": "description",
			"read_only": 1,
			"no_copy": 0,
			"depends_on": "eval:doc.maintenance_source",
			"print_hide": 1,
		},
		{
			"fieldname": "maintenance_source",
			"label": "Maintenance Source",
			"fieldtype": "Dynamic Link",
			"options": "maintenance_source_doctype",
			"insert_after": "maintenance_source_doctype",
			"read_only": 1,
			"depends_on": "eval:doc.maintenance_source",
			"print_hide": 1,
		},
		{
			"fieldname": "equipment_codes",
			"label": "Equipment Codes",
			"fieldtype": "Small Text",
			"insert_after": "maintenance_source",
			"read_only": 1,
			"depends_on": "eval:doc.maintenance_source",
		},
	]


def make_custom_fields():
	create_custom_fields(
		{
			"Quotation Item": billing_fields(),
			"Sales Order Item": billing_fields(),
			"Sales Invoice Item": billing_fields(),
			"Purchase Invoice": [
				{
					"fieldname": "external_service_dispatch",
					"label": "External Service Dispatch",
					"fieldtype": "Link",
					"options": "External Service Dispatch",
					"insert_after": "supplier",
					"read_only": 1,
					"no_copy": 1,
				}
			],
			"Stock Entry": [
				{
					"fieldname": "equipment_maintenance_report",
					"label": "Equipment Maintenance Report",
					"fieldtype": "Link",
					"options": "Equipment Maintenance Report",
					"insert_after": "stock_entry_type",
					"read_only": 1,
					"no_copy": 1,
				}
			],
		},
		update=True,
	)
