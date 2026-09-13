"""Pruebas del endpoint POST /api/pdf (descarga directa de PDF).

No toca /api/generate ni el resto de contratos: solo cubre validación,
cabeceras de descarga, generación exitosa, sanitización y fallo del motor.
"""

import re
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class PdfEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_empty_html_rejected(self):
        for bad in ("", "   ", "\n\t "):
            with self.subTest(bad=repr(bad)):
                result = self.client.post("/api/pdf", json={"html": bad})
                self.assertEqual(result.status_code, 422)

    def test_missing_html_rejected(self):
        self.assertEqual(self.client.post("/api/pdf", json={}).status_code, 422)

    def test_oversized_html_rejected(self):
        # Más de 2M de caracteres: lo frena la validación Pydantic (422).
        result = self.client.post("/api/pdf", json={"html": "x" * 2000001})
        self.assertIn(result.status_code, (413, 422))
        # Menos de 2M de caracteres pero más de 2MB en bytes: lo frena el
        # endpoint con 413 (€ = 3 bytes en UTF-8; 700k chars ≈ 2.1MB).
        result = self.client.post("/api/pdf", json={"html": "€" * 700000})
        self.assertIn(result.status_code, (413, 422))

    def test_success_pdf_headers_and_magic(self):
        html = (
            "<h1>Plan de 18 meses</h1>"
            "<p>Utilidad: $1,220 | CAT 35.1% | Saldo $18,400</p>"
            "<table><thead><tr><th>Mes</th><th>Pago</th></tr></thead>"
            "<tbody><tr><td>1</td><td>$1690</td></tr></tbody></table>"
        )
        result = self.client.post("/api/pdf", json={"html": html})
        self.assertEqual(result.status_code, 200)
        self.assertIn("application/pdf", result.headers["content-type"])
        disp = result.headers.get("content-disposition", "")
        self.assertIn("attachment", disp)
        self.assertRegex(disp, r'filename="glintmesh-interface-\d+\.pdf"')
        self.assertTrue(result.content.startswith(b"%PDF"))
        self.assertGreater(len(result.content), 500)

    def test_no_auth_required_but_accepted(self):
        result = self.client.post(
            "/api/pdf",
            json={"html": "<p>hola</p>"},
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(result.status_code, 200)
        self.assertIn("application/pdf", result.headers["content-type"])

    def test_scripts_and_remote_urls_are_sanitized(self):
        html = (
            '<script>alert("xss")</script>'
            '<img src="https://example.com/x.png">'
            '<img src="file:///etc/passwd">'
            "<p>Contenido real $482,300</p>"
        )
        result = self.client.post("/api/pdf", json={"html": html})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.content.startswith(b"%PDF"))
        clean = main._sanitize_html_for_pdf(html)
        self.assertNotIn("alert", clean)
        self.assertNotIn("example.com", clean)
        self.assertNotIn("file://", clean)
        self.assertIn("Contenido real", clean)

    def test_script_only_has_no_printable_content(self):
        result = self.client.post(
            "/api/pdf", json={"html": "<script>alert(1)</script>"}
        )
        self.assertEqual(result.status_code, 422)

    def test_embedded_png_image_allowed(self):
        # PNG real de 1x1 (transparente).
        png = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        result = self.client.post(
            "/api/pdf", json={"html": f"<p>chart</p><img src=\"{png}\" alt=\"x\">"}
        )
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.content.startswith(b"%PDF"))

    def test_engine_failure_is_500(self):
        with patch.object(
            main, "_build_pdf_bytes", side_effect=RuntimeError("engine down")
        ):
            result = self.client.post("/api/pdf", json={"html": "<p>hola</p>"})
        self.assertEqual(result.status_code, 500)

    def test_filename_pattern(self):
        self.assertRegex(
            f"glintmesh-interface-1234567890.pdf",
            r"^glintmesh-interface-\d+\.pdf$",
        )
        self.assertTrue(re.match(r"^attachment; ", 'attachment; filename="x"'))


if __name__ == "__main__":
    unittest.main()
