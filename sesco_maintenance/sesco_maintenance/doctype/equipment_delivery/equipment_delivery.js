frappe.ui.form.on("Equipment Delivery", {
	setup(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Equipment Activity"];
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Ready Equipment"), () => {
				if (!frm.doc.customer) {
					frappe.msgprint(__("Select the customer first."));
					return;
				}
				sesco_maintenance.get_equipment(frm, "delivery", {}, frm.doc.customer);
			});
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Print Delivery Note"), () => sesco_maintenance.print(frm, "Equipment Delivery Note"));
		}
	},

	customer(frm) {
		// equipment belongs to one customer, so a new customer starts an empty list
		if ((frm.doc.items || []).some((r) => r.equipment)) {
			frm.clear_table("items");
			frm.refresh_field("items");
		}
	},
});
