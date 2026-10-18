frappe.ui.form.on("Equipment Receipt", {
	setup(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Equipment Activity"];
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Add by Quantity"), () => add_by_quantity(frm));
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Print QR Labels"), () => sesco_maintenance.print(frm, "Equipment Labels"));
		}
	},

	scan_barcode(frm) {
		const code = (frm.doc.scan_barcode || "").trim().toUpperCase();
		if (!code) return;
		const clear = () => frm.set_value("scan_barcode", "");
		if (!frm.doc.customer) {
			frappe.msgprint(__("Select the customer first."));
			clear();
			return;
		}
		if ((frm.doc.items || []).some((r) => r.equipment === code)) {
			frappe.show_alert({ message: __("Equipment {0} is already in this receipt.", [code]), indicator: "orange" });
			clear();
			return;
		}
		frappe
			.call({
				method: "sesco_maintenance.api.get_equipment_for_receipt",
				args: { code, customer: frm.doc.customer, doctype: frm.doctype, docname: frm.doc.name },
			})
			.then((r) => {
				const res = r.message || {};
				if (res.error) {
					frappe.show_alert({ message: res.error, indicator: "red" }, 7);
					frappe.utils.play_sound("error");
				} else {
					const eq = res.equipment;
					frm.doc.items = (frm.doc.items || []).filter((row) => row.equipment || row.equipment_type);
					frm.add_child("items", {
						equipment: eq.name,
						equipment_type: eq.equipment_type,
						route: eq.route,
						last_hydrotest_date: eq.last_hydrotest_date,
					});
					frm.refresh_field("items");
					let message = __("Added {0}", [eq.name]);
					if (eq.hydrotest === "overdue") message += " · " + __("Hydrostatic test is overdue");
					if (eq.hydrotest === "due") message += " · " + __("Hydrostatic test is due soon");
					frappe.show_alert({ message, indicator: eq.hydrotest ? "orange" : "green" });
				}
				clear();
			});
	},
});

frappe.ui.form.on("Equipment Receipt Item", {
	equipment_type(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.equipment_type || row.equipment) return;
		frappe.db.get_value("Equipment Type", row.equipment_type, "default_route").then((r) => {
			frappe.model.set_value(cdt, cdn, "route", r.message.default_route);
		});
	},
});

function add_by_quantity(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Add New Equipment"),
		fields: [
			{ fieldname: "equipment_type", fieldtype: "Link", options: "Equipment Type", label: __("Equipment Type"), reqd: 1 },
			{ fieldname: "qty", fieldtype: "Int", label: __("Quantity"), reqd: 1, default: 1 },
			{
				fieldname: "last_hydrotest_date",
				fieldtype: "Date",
				label: __("Last Hydrostatic Test"),
				description: __("Optional. From the cylinder stamp, for CO2 cylinders."),
			},
		],
		primary_action_label: __("Add"),
		async primary_action(values) {
			if (values.qty < 1 || values.qty > 500) {
				frappe.msgprint(__("Quantity must be between 1 and 500."));
				return;
			}
			const r = await frappe.db.get_value("Equipment Type", values.equipment_type, "default_route");
			frm.doc.items = (frm.doc.items || []).filter((row) => row.equipment || row.equipment_type);
			for (let i = 0; i < values.qty; i++) {
				frm.add_child("items", {
					equipment_type: values.equipment_type,
					route: r.message.default_route,
					last_hydrotest_date: values.last_hydrotest_date,
				});
			}
			frm.refresh_field("items");
			dialog.hide();
		},
	});
	dialog.show();
}
