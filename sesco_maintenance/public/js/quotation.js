frappe.ui.form.on("Quotation", {
	refresh(frm) {
		sesco_maintenance.add_get_items_button(frm, "party_name");
	},
});
