"""Billing customers from maintenance reports through the normal Quotation / Sales Order flow.

Source rows (Maintenance Report Item with result OK, External Service Dispatch Item returned OK)
carry `billed_in_doctype` / `billed_in`. A row is billable while it is empty, or points to a
cancelled document or a lost quotation.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import today

SOURCE_TABLES = {
	"Equipment Maintenance Report": "Maintenance Report Item",
	"External Service Dispatch": "External Service Dispatch Item",
}
BILLING_DOCTYPES = ("Quotation", "Sales Order")


def is_active_billing(doctype, name):
	if not (doctype and name):
		return False
	values = frappe.db.get_value(doctype, name, ["docstatus", "status"], as_dict=True)
	if not values or values.docstatus != 1:
		return False
	return not (doctype == "Quotation" and values.status == "Lost")


def split_codes(text):
	return [c.strip() for c in (text or "").replace(",", "\n").split("\n") if c.strip()]


@frappe.whitelist()
def get_billable_sources(customer):
	"""[{source_doctype, source_name, date, equipment: [{code, equipment_type}]}] for the customer."""
	rows = frappe.db.sql(
		"""
		select 'Equipment Maintenance Report' as source_doctype, r.parent as source_name, p.posting_date as date,
			r.equipment, r.equipment_type, r.billed_in_doctype, r.billed_in
		from `tabMaintenance Report Item` r
		join `tabEquipment Maintenance Report` p on p.name = r.parent
		where p.docstatus = 1 and r.customer = %(customer)s and r.result = 'OK'
		union all
		select 'External Service Dispatch', r.parent, r.return_date,
			r.equipment, r.equipment_type, r.billed_in_doctype, r.billed_in
		from `tabExternal Service Dispatch Item` r
		join `tabExternal Service Dispatch` p on p.name = r.parent
		where p.docstatus = 1 and r.customer = %(customer)s and r.return_status = 'Returned OK'
		""",
		{"customer": customer},
		as_dict=True,
	)
	sources = {}
	for row in rows:
		if is_active_billing(row.billed_in_doctype, row.billed_in):
			continue
		key = (row.source_doctype, row.source_name)
		src = sources.setdefault(
			key, {"source_doctype": row.source_doctype, "source_name": row.source_name, "date": row.date, "equipment": []}
		)
		if row.date and (not src["date"] or row.date > src["date"]):
			src["date"] = row.date
		src["equipment"].append({"code": row.equipment, "equipment_type": row.equipment_type})
	return sorted(sources.values(), key=lambda s: (str(s["date"]), s["source_name"]))


def get_fallback_rate(item_code):
	"""Standard selling rate, used when the customer's price list has no price for the item."""
	price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
	return frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": price_list, "selling": 1}, "price_list_rate") or 0


def get_customer_rate(customer, equipment_type):
	"""Customer price list rate for the equipment type's service item, else the standard rate."""
	item_code = frappe.get_cached_value("Equipment Type", equipment_type, "service_item")
	if not item_code:
		return 0
	price_list = frappe.get_cached_value("Customer", customer, "default_price_list")
	rate = None
	if price_list:
		rate = frappe.db.get_value(
			"Item Price", {"item_code": item_code, "price_list": price_list, "selling": 1}, "price_list_rate"
		)
	return rate or get_fallback_rate(item_code)


def build_lines(customer, sources):
	"""One line per source and equipment type: service item x count."""
	available = {(s["source_doctype"], s["source_name"]): s for s in get_billable_sources(customer)}
	lines = []
	for wanted in sources:
		key = (wanted.get("source_doctype"), wanted.get("source_name"))
		src = available.get(key)
		if not src:
			frappe.throw(_("{0} {1} has nothing left to bill for {2}.").format(_(key[0]), key[1], customer))
		by_type = defaultdict(list)
		for eq in src["equipment"]:
			by_type[eq["equipment_type"]].append(eq["code"])
		for equipment_type, codes in by_type.items():
			item_code = frappe.get_cached_value("Equipment Type", equipment_type, "service_item")
			if not item_code:
				frappe.throw(_("Set the Customer Service Item on equipment type {0}.").format(equipment_type))
			lines.append(
				{
					"item_code": item_code,
					"qty": len(codes),
					"maintenance_source_doctype": key[0],
					"maintenance_source": key[1],
					"equipment_codes": "\n".join(codes),
					"fallback_rate": get_fallback_rate(item_code),
				}
			)
	return lines


def _append_lines(doc, customer, sources):
	doc.items = [row for row in doc.items if row.item_code]
	fallback = {}
	for line in build_lines(customer, sources):
		rate = line.pop("fallback_rate")
		if doc.doctype == "Sales Order":
			line["delivery_date"] = doc.delivery_date or today()
		row = doc.append("items", line)
		fallback[row.idx] = rate

	doc.set_missing_values()
	for row in doc.items:
		if not row.rate and fallback.get(row.idx):
			row.price_list_rate = row.rate = fallback[row.idx]
	doc.calculate_taxes_and_totals()
	return doc


def _customer_of(doc):
	if doc.doctype == "Quotation":
		if doc.quotation_to != "Customer":
			frappe.throw(_("Maintenance can be billed to customers only."))
		return doc.party_name
	return doc.customer


@frappe.whitelist()
def add_maintenance_items(target_doc, sources):
	"""'Get Items From > Maintenance Reports' on an open Quotation / Sales Order."""
	doc = frappe.get_doc(frappe.parse_json(target_doc))
	if doc.doctype not in BILLING_DOCTYPES:
		frappe.throw(_("Not supported for {0}.").format(doc.doctype))
	frappe.has_permission(doc.doctype, "write" if not doc.is_new() else "create", throw=True)
	customer = _customer_of(doc)
	if not customer:
		frappe.throw(_("Select the customer first."))
	return _append_lines(doc, customer, frappe.parse_json(sources))


@frappe.whitelist()
def make_billing_doc(source_doctype, source_name, target_doctype, customer=None):
	"""New Quotation / Sales Order from one maintenance report or dispatch (button on the source)."""
	if target_doctype not in BILLING_DOCTYPES or source_doctype not in SOURCE_TABLES:
		frappe.throw(_("Not supported."))
	frappe.get_doc(source_doctype, source_name).check_permission("read")
	frappe.has_permission(target_doctype, "create", throw=True)

	customers = sorted(
		set(
			frappe.get_all(
				SOURCE_TABLES[source_doctype], filters={"parent": source_name}, pluck="customer"
			)
		)
	)
	customer = customer or next(
		(c for c in customers if any(s["source_name"] == source_name for s in get_billable_sources(c))), None
	)
	if not customer:
		frappe.throw(_("{0} has nothing left to bill.").format(source_name))

	doc = frappe.new_doc(target_doctype)
	doc.transaction_date = today()
	doc.company = frappe.db.get_single_value("Equipment Maintenance Settings", "company") or doc.company
	if target_doctype == "Quotation":
		doc.quotation_to = "Customer"
		doc.party_name = customer
	else:
		doc.customer = customer
		doc.delivery_date = today()
	return _append_lines(doc, customer, [{"source_doctype": source_doctype, "source_name": source_name}])


def _source_rows(item):
	table = SOURCE_TABLES.get(item.get("maintenance_source_doctype"))
	if not (table and item.get("maintenance_source")):
		return []
	codes = split_codes(item.get("equipment_codes"))
	return frappe.get_all(
		table,
		filters={"parent": item.maintenance_source, "equipment": ("in", codes or [""])},
		fields=["name", "equipment", "billed_in_doctype", "billed_in"],
	)


def _own_names(doc):
	"""This document plus the quotations a sales order was made from."""
	names = {doc.name}
	for item in doc.items:
		if item.get("prevdoc_docname"):
			names.add(item.prevdoc_docname)
	return names


def validate_billing(doc, method=None):
	"""Quotation / Sales Order validate: no equipment billed twice."""
	own = _own_names(doc)
	seen = set()
	for item in doc.items:
		if not item.get("maintenance_source"):
			continue
		codes = split_codes(item.equipment_codes)
		rows = _source_rows(item)
		found = {r.equipment for r in rows}
		missing = [c for c in codes if c not in found]
		if missing:
			frappe.throw(
				_("Row {0}: {1} is not in {2}.").format(item.idx, ", ".join(missing), item.maintenance_source)
			)
		for r in rows:
			key = (item.maintenance_source, r.equipment)
			if key in seen:
				frappe.throw(_("Row {0}: Equipment {1} is billed twice in this document.").format(item.idx, r.equipment))
			seen.add(key)
			if r.billed_in and r.billed_in not in own and is_active_billing(r.billed_in_doctype, r.billed_in):
				frappe.throw(
					_("Row {0}: Equipment {1} from {2} is already billed in {3}.").format(
						item.idx, r.equipment, item.maintenance_source, r.billed_in
					)
				)


def mark_billed(doc, method=None):
	own = _own_names(doc)
	for item in doc.items:
		table = SOURCE_TABLES.get(item.get("maintenance_source_doctype"))
		for r in _source_rows(item):
			if r.billed_in in own and is_active_billing(r.billed_in_doctype, r.billed_in):
				continue  # already held by the quotation this order came from
			frappe.db.set_value(table, r.name, {"billed_in_doctype": doc.doctype, "billed_in": doc.name})


def unmark_billed(doc, method=None):
	for table in SOURCE_TABLES.values():
		for name in frappe.get_all(table, filters={"billed_in_doctype": doc.doctype, "billed_in": doc.name}, pluck="name"):
			frappe.db.set_value(table, name, {"billed_in_doctype": None, "billed_in": None})
