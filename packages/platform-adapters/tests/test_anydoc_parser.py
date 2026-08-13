from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from platform_adapters.parsers.anydoc_parser import (
    AnydocTextExtractor,
    DocumentTextExtractionError,
    UnsupportedDocumentTypeError,
)


SAMPLES = Path(__file__).parent / "samples" / "generated"


class AnydocTextExtractorTest(unittest.TestCase):
    def setUp(self):
        self.extractor = AnydocTextExtractor()

    def test_extracts_common_office_and_pdf_formats(self):
        expectations = {
            "invoice.docx": "SAMPLE-001",
            "invoice.pdf": "SAMPLE-001",
            "invoice.pptx": "SAMPLE-001",
            "invoice.xlsx": "SAMPLE-001",
        }

        for filename, expected in expectations.items():
            with self.subTest(filename=filename):
                path = SAMPLES / filename
                result = self.extractor.extract(path.read_bytes(), filename)
                self.assertIn(expected, result.content)
                self.assertEqual(result.source_format, path.suffix.lstrip("."))
                self.assertEqual(result.engine, "anydoc")

    def test_accepts_legacy_doc_extension_before_parsing(self):
        with self.assertRaises(DocumentTextExtractionError) as raised:
            self.extractor.extract(b"not-a-real-doc", "legacy.doc")
        self.assertNotIsInstance(raised.exception, UnsupportedDocumentTypeError)

    def test_rejects_unsupported_extension(self):
        with self.assertRaises(UnsupportedDocumentTypeError):
            self.extractor.extract(b"image", "scan.png")

    def test_rejects_empty_document(self):
        with self.assertRaises(DocumentTextExtractionError):
            self.extractor.extract(b"", "empty.docx")


if __name__ == "__main__":
    unittest.main()
