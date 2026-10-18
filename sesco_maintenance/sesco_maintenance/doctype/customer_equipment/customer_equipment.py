from frappe.model.document import Document


class CustomerEquipment(Document):
	"""Customer-owned equipment. Created by Equipment Receipt; every change comes from a document
	through sesco_maintenance.movement.apply_movement, never from manual edits."""

	pass
