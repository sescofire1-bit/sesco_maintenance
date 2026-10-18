// Shared helpers for SESCO Maintenance forms, Quotation and Sales Order.
frappe.provide("sesco_maintenance");

// "Get ..." buttons: add equipment that is in the right state and not held by another draft.
sesco_maintenance.get_equipment = function (frm, purpose, row_defaults, customer) {
	const exclude = (frm.doc.items || []).map((r) => r.equipment).filter(Boolean);
	return frappe
		.call({
			method: "sesco_maintenance.api.get_available_equipment",
			args: { purpose, customer, doctype: frm.doctype, docname: frm.doc.name, exclude },
			freeze: true,
		})
		.then((r) => {
			const list = r.message || [];
			if (!list.length) {
				frappe.msgprint(exclude.length ? __("Nothing more to add.") : __("No equipment is available for this document."));
				return;
			}
			const child = frappe.meta.get_docfield(frm.doctype, "items").options;
			frm.doc.items = (frm.doc.items || []).filter((r) => r.equipment);
			list.forEach((eq) => {
				const row = { equipment: eq.name, equipment_type: eq.equipment_type };
				if (frappe.meta.has_field(child, "customer")) row.customer = eq.customer;
				frm.add_child("items", Object.assign(row, row_defaults || {}));
			});
			frm.refresh_field("items");
			const due = list.filter((e) => e.hydrotest).length;
			frappe.show_alert({
				message:
					__("Added {0} equipment", [list.length]) +
					(due ? " · " + __("{0} need a hydrostatic test", [due]) : ""),
				indicator: due ? "orange" : "green",
			});
		});
};

sesco_maintenance.print = function (frm, print_format) {
	const url =
		"/printview?doctype=" + encodeURIComponent(frm.doctype) +
		"&name=" + encodeURIComponent(frm.doc.name) +
		"&format=" + encodeURIComponent(print_format) +
		"&no_letterhead=1";
	window.open(url, "_blank");
};

// Source documents: Bill Customer > Quotation / Sales Order
sesco_maintenance.add_billing_buttons = function (frm, has_billable) {
	if (!has_billable) return;
	["Quotation", "Sales Order"].forEach((target) => {
		if (!frappe.model.can_create(target)) return;
		frm.add_custom_button(__(target), () => sesco_maintenance.make_billing(frm, target), __("Bill Customer"));
	});
};

sesco_maintenance.make_billing = function (frm, target_doctype) {
	frappe
		.call({
			method: "sesco_maintenance.billing.make_billing_doc",
			args: { source_doctype: frm.doctype, source_name: frm.doc.name, target_doctype },
			freeze: true,
		})
		.then((r) => {
			if (!r.message) return;
			const doc = frappe.model.sync(r.message)[0];
			frappe.set_route("Form", doc.doctype, doc.name);
		});
};

// Quotation / Sales Order: Get Items From > Maintenance Reports
sesco_maintenance.add_get_items_button = function (frm, customer_field) {
	if (frm.doc.docstatus !== 0) return;
	frm.add_custom_button(
		__("Maintenance Reports"),
		() => sesco_maintenance.pick_sources(frm, customer_field),
		__("Get Items From")
	);
};

sesco_maintenance.pick_sources = function (frm, customer_field) {
	const customer = frm.doc[customer_field];
	if (!customer || (frm.doctype === "Quotation" && frm.doc.quotation_to !== "Customer")) {
		frappe.msgprint(__("Select the customer first."));
		return;
	}
	frappe.call({ method: "sesco_maintenance.billing.get_billable_sources", args: { customer } }).then((r) => {
		const already = new Set((frm.doc.items || []).map((i) => i.maintenance_source).filter(Boolean));
		const options = (r.message || [])
			.filter((s) => !already.has(s.source_name))
			.map((s) => ({
				label: [
					s.source_name,
					__(s.source_doctype),
					frappe.datetime.str_to_user(s.date),
					__("{0} equipment", [s.equipment.length]),
				].join(" · "),
				value: s.source_doctype + "::" + s.source_name,
				checked: 0,
			}));
		if (!options.length) {
			frappe.msgprint(__("Nothing is waiting to be billed for {0}.", [customer]));
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: __("Get Items From Maintenance Reports"),
			fields: [
				{ fieldname: "sources", fieldtype: "MultiCheck", label: __("Reports"), options, columns: 1 },
				{
					fieldtype: "HTML",
					options: `<p class="text-muted small">${__("You can choose more than one report. Damaged equipment is never billed.")}</p>`,
				},
			],
			primary_action_label: __("Get Items"),
			primary_action(values) {
				const sources = (values.sources || []).map((v) => {
					const [source_doctype, source_name] = v.split("::");
					return { source_doctype, source_name };
				});
				if (!sources.length) {
					frappe.msgprint(__("Choose at least one report."));
					return;
				}
				dialog.hide();
				frappe
					.call({
						method: "sesco_maintenance.billing.add_maintenance_items",
						args: { target_doc: frm.doc, sources },
						freeze: true,
					})
					.then((res) => {
						if (!res.message) return;
						frappe.model.sync(res.message);
						frm.dirty();
						frm.refresh();
					});
			},
		});
		dialog.show();
	});
};
