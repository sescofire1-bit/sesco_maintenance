"""Estimated cost and profit per Equipment Receipt (no Projects).

Revenue: customer price list rate of the service item for every equipment not found damaged.
Accessories: each maintenance report's accessories cost split evenly over its rows.
Supplier: the equipment type's estimated supplier rate for every equipment returned OK.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from sesco_maintenance.billing import get_customer_rate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = {"docstatus": 1}
	if filters.get("customer"):
		conditions["customer"] = filters.customer
	if filters.get("from_date") and filters.get("to_date"):
		conditions["posting_date"] = ("between", [filters.from_date, filters.to_date])

	receipts = frappe.get_all(
		"Equipment Receipt", filters=conditions, fields=["name", "customer", "posting_date"], order_by="posting_date desc"
	)
	if not receipts:
		return get_columns(), []
	names = [r.name for r in receipts]

	items = defaultdict(list)
	for row in frappe.get_all(
		"Equipment Receipt Item", filters={"parent": ("in", names)}, fields=["parent", "equipment", "equipment_type"]
	):
		items[row.parent].append(row)

	damaged = defaultdict(set)
	accessories = defaultdict(float)
	for row in frappe.db.sql(
		"""
		select r.equipment_receipt, r.equipment, r.result,
			p.total_accessories_cost / (select count(*) from `tabMaintenance Report Item` c where c.parent = p.name) as share
		from `tabMaintenance Report Item` r
		join `tabEquipment Maintenance Report` p on p.name = r.parent
		where p.docstatus = 1 and r.equipment_receipt in %(names)s
		""",
		{"names": names},
		as_dict=True,
	):
		accessories[row.equipment_receipt] += flt(row.share)
		if row.result == "Damaged":
			damaged[row.equipment_receipt].add(row.equipment)

	supplier = defaultdict(float)
	for row in frappe.db.sql(
		"""
		select r.equipment_receipt, r.equipment, r.return_status, t.supplier_rate
		from `tabExternal Service Dispatch Item` r
		join `tabExternal Service Dispatch` p on p.name = r.parent
		left join `tabEquipment Type` t on t.name = r.equipment_type
		where p.docstatus = 1 and r.equipment_receipt in %(names)s and r.return_status != 'At Supplier'
		""",
		{"names": names},
		as_dict=True,
	):
		if row.return_status == "Returned OK":
			supplier[row.equipment_receipt] += flt(row.supplier_rate)
		else:
			damaged[row.equipment_receipt].add(row.equipment)

	data = []
	for r in receipts:
		revenue = sum(
			get_customer_rate(r.customer, i.equipment_type) for i in items[r.name] if i.equipment not in damaged[r.name]
		)
		profit = revenue - accessories[r.name] - supplier[r.name]
		data.append(
			{
				"receipt": r.name,
				"customer": r.customer,
				"posting_date": r.posting_date,
				"equipment_count": len(items[r.name]),
				"damaged_count": len(damaged[r.name]),
				"revenue": revenue,
				"accessories_cost": accessories[r.name],
				"supplier_cost": supplier[r.name],
				"profit": profit,
				"margin": (profit / revenue * 100) if revenue else 0,
			}
		)
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Equipment Receipt"), "fieldname": "receipt", "fieldtype": "Link", "options": "Equipment Receipt", "width": 150},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
		{"label": _("Receipt Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Equipment"), "fieldname": "equipment_count", "fieldtype": "Int", "width": 90},
		{"label": _("Damaged"), "fieldname": "damaged_count", "fieldtype": "Int", "width": 80},
		{"label": _("Estimated Revenue"), "fieldname": "revenue", "fieldtype": "Currency", "width": 130},
		{"label": _("Accessories Cost"), "fieldname": "accessories_cost", "fieldtype": "Currency", "width": 130},
		{"label": _("Supplier Cost"), "fieldname": "supplier_cost", "fieldtype": "Currency", "width": 120},
		{"label": _("Estimated Profit"), "fieldname": "profit", "fieldtype": "Currency", "width": 130},
		{"label": _("Margin %"), "fieldname": "margin", "fieldtype": "Percent", "width": 90},
	]
