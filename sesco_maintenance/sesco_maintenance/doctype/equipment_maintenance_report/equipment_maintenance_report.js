frappe.ui.form.on("Equipment Maintenance Report", {
	setup(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Stock Entry", "Equipment Activity"];
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Internal Equipment"), () =>
				sesco_maintenance.get_equipment(frm, "maintenance", { result: "OK" })
			);
		}
		if (frm.doc.docstatus === 1) {
			const billable = (frm.doc.items || []).some((r) => r.result === "OK" && !r.billed_in);
			sesco_maintenance.add_billing_buttons(frm, billable);
		}
	},
});

frappe.ui.form.on("Maintenance Accessory", {
	item_code: update_accessory,
	qty: update_accessory,
});

function update_accessory(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.item_code) return;
	frappe.call("sesco_maintenance.api.get_accessory_details", { item_code: row.item_code }).then((r) => {
		const d = r.message;
		frappe.model.set_value(cdt, cdn, {
			available_qty: d.available_qty,
			valuation_rate: d.valuation_rate,
			amount: flt(row.qty) * d.valuation_rate,
		});
		if (flt(row.qty) > d.available_qty) {
			frappe.show_alert(
				{ message: __("Only {0} available in {1}", [d.available_qty, d.warehouse]), indicator: "orange" },
				6
			);
		}
	});
}
