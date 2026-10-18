import base64
import io


def get_qr_svg(text, scale=3):
	"""Data URI of a QR code (SVG) for print formats. pyqrcode ships with Frappe."""
	import pyqrcode

	buffer = io.BytesIO()
	pyqrcode.create(str(text)).svg(buffer, scale=scale, quiet_zone=1, xmldecl=False, svgns=True)
	return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode()
