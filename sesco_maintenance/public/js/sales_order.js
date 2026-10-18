frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		sesco_maintenance.add_get_items_button(frm, "customer");
	},
});
