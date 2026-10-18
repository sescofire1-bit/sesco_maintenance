import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = {}
	for field in ("customer", "status", "equipment_type"):
		if filters.get(field):
			conditions[field] = filters.get(field)
	if filters.get("equipment"):
		conditions["name"] = ("like", f"%{filters.equipment.strip()}%")

	equipment = frappe.get_all(
		"Customer Equipment",
		filters=conditions,
		fields=["name", "customer", "equipment_type", "status", "current_location"],
		order_by="name asc",
	)
	last = {}
	if equipment:
		for row in frappe.db.sql(
			"""
			select a.equipment, a.activity_date, a.reference_doctype, a.reference_name
			from `tabEquipment Activity` a
			join (select equipment, max(creation) as last_creation from `tabEquipment Activity`
				where equipment in %(codes)s group by equipment) m
				on m.equipment = a.equipment and m.last_creation = a.creation
			""",
			{"codes": [e.name for e in equipment]},
			as_dict=True,
		):
			last[row.equipment] = row

	data = []
	for e in equipment:
		act = last.get(e.name, {})
		data.append(
			{
				"equipment": e.name,
				"customer": e.customer,
				"equipment_type": e.equipment_type,
				"status": _(e.status),
				"current_location": e.current_location,
				"since": act.get("activity_date"),
				"last_doctype": act.get("reference_doctype"),
				"last_document": act.get("reference_name"),
			}
		)
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Equipment"), "fieldname": "equipment", "fieldtype": "Link", "options": "Customer Equipment", "width": 130},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
		{"label": _("Equipment Type"), "fieldname": "equipment_type", "fieldtype": "Link", "options": "Equipment Type", "width": 170},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": _("Current Location"), "fieldname": "current_location", "fieldtype": "Data", "width": 170},
		{"label": _("Since"), "fieldname": "since", "fieldtype": "Date", "width": 100},
		{"label": _("Document Type"), "fieldname": "last_doctype", "fieldtype": "Link", "options": "DocType", "hidden": 1},
		{"label": _("Last Document"), "fieldname": "last_document", "fieldtype": "Dynamic Link", "options": "last_doctype", "width": 160},
	]
