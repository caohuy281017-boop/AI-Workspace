from __future__ import annotations

import tempfile
import unittest
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from file_first_ai.adapters.docling_parser import (
    DoclingFileParser,
    NonLocalFileError,
    UnsupportedFileTypeError,
)
from file_first_ai.domain import FileReference


MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class Label:
    value = "text"


class Origin:
    value = "TOPLEFT"


@dataclass
class FakeBox:
    l: float = 10
    t: float = 20
    r: float = 110
    b: float = 40
    coord_origin: Origin = Origin()


class FakeItem:
    label = Label()
    self_ref = "#/texts/0"
    parent = None
    text = "Sample invoice"
    prov = (SimpleNamespace(page_no=1, bbox=FakeBox(), charspan=(0, 14)),)
    data = None


class FakeDocument:
    pages = {1: SimpleNamespace(size=SimpleNamespace(height=800))}

    def iterate_items(self):
        yield FakeItem(), 1


class RecordingConverter:
    def __init__(self):
        self.paths = []

    def convert(self, path):
        self.paths.append(path)
        return SimpleNamespace(document=FakeDocument())


class DoclingFileParserTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.converter = RecordingConverter()
        self.parser = DoclingFileParser(converter=self.converter)

    def source(self, extension):
        path = self.root / f"sample{extension}"
        # Converter is injected in unit tests; format validity belongs to the
        # opt-in integration suite that runs the real Docling package.
        path.write_bytes(f"sample {extension}".encode())
        return FileReference(
            f"file-{extension[1:]}",
            "workspace-1",
            path.name,
            MEDIA_TYPES[extension],
            path.stat().st_size,
            str(path),
        )

    def test_supports_required_media_types(self):
        self.assertEqual(set(self.parser.supported_media_types()), set(MEDIA_TYPES.values()))

    def test_normalizes_each_required_format(self):
        for extension in MEDIA_TYPES:
            with self.subTest(extension=extension):
                result = self.parser.parse(self.source(extension))
                self.assertEqual(result.parser, "docling")
                self.assertEqual(result.metadata["normalized_schema_version"], "1.0")
                self.assertEqual(result.metadata["source_format"], extension[1:])
                self.assertEqual(result.blocks[0].kind, "text")
                self.assertEqual(result.blocks[0].text, "Sample invoice")
                self.assertEqual(result.blocks[0].bounds.page, 1)
                self.assertNotIn("docling", type(result.blocks[0]).__module__)

    def test_rejects_object_storage_uri_until_materialized(self):
        source = FileReference(
            "file-1", "workspace-1", "x.pdf", "application/pdf", 1, "s3://bucket/x.pdf"
        )
        with self.assertRaises(NonLocalFileError):
            self.parser.parse(source)

    def test_rejects_mismatched_type(self):
        path = self.root / "sample.txt"
        path.write_text("sample")
        source = FileReference(
            "file-1", "workspace-1", path.name, "text/plain", 6, str(path)
        )
        with self.assertRaises(UnsupportedFileTypeError):
            self.parser.parse(source)


if __name__ == "__main__":
    unittest.main()
