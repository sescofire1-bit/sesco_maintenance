app_name = "sesco_maintenance"
app_title = "SESCO Maintenance"
app_publisher = "SESCO"
app_description = "Maintenance of customer-owned equipment (fire extinguishers first) on ERPNext"
app_email = ""
app_license = "mit"

required_apps = ["erpnext"]

# sesco_common.js holds the shared form helpers; Quotation / Sales Order get "Get Items From > Maintenance Reports"
doctype_js = {
	"Quotation": ["public/js/sesco_common.js", "public/js/quotation.js"],
	"Sales Order": ["public/js/sesco_common.js", "public/js/sales_order.js"],
	"Equipment Receipt": "public/js/sesco_common.js",
	"Equipment Maintenance Report": "public/js/sesco_common.js",
	"External Service Dispatch": "public/js/sesco_common.js",
	"Equipment Delivery": "public/js/sesco_common.js",
}

doc_events = {
	"Quotation": {
		"validate": "sesco_maintenance.billing.validate_billing",
		"on_submit": "sesco_maintenance.billing.mark_billed",
		"on_cancel": "sesco_maintenance.billing.unmark_billed",
	},
	"Sales Order": {
		"validate": "sesco_maintenance.billing.validate_billing",
		"on_submit": "sesco_maintenance.billing.mark_billed",
		"on_cancel": "sesco_maintenance.billing.unmark_billed",
	},
	"Purchase Invoice": {
		"on_submit": "sesco_maintenance.sesco_maintenance.doctype.external_service_dispatch.external_service_dispatch.link_purchase_invoice",
		"on_cancel": "sesco_maintenance.sesco_maintenance.doctype.external_service_dispatch.external_service_dispatch.unlink_purchase_invoice",
	},
}

after_install = "sesco_maintenance.install.after_install"
after_migrate = "sesco_maintenance.install.after_migrate"

jinja = {
	"methods": ["sesco_maintenance.utils.get_qr_svg"],
}
