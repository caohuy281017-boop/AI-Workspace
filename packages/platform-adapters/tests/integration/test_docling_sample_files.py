"""Opt-in real Docling smoke tests.

Run after installing ``.[docling]`` and generating fixtures:
    python tests/samples/create_samples.py
    python -m unittest tests.integration.test_docling_sample_files -v

PDF conversion can download approved model artifacts on first use. CI should
prefetch pinned artifacts instead of allowing implicit network access.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from platform_adapters.parsers.docling_parser import DoclingFileParser
from platform_core.domain import FileReference


SAMPLES = Path(__file__).parents[1] / "samples" / "generated"
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@unittest.skipUnless(importlib.util.find_spec("docling"), "install .[docling]")
class DoclingSampleIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all((SAMPLES / f"invoice{ext}").exists() for ext in MEDIA_TYPES):
            raise unittest.SkipTest("run tests/samples/create_samples.py")
        cls.parser = DoclingFileParser()

    def test_real_samples_normalize_without_docling_objects(self):
        for extension, media_type in MEDIA_TYPES.items():
            with self.subTest(extension=extension):
                path = SAMPLES / f"invoice{extension}"
                source = FileReference(
                    f"sample-{extension[1:]}",
                    "test-workspace",
                    path.name,
                    media_type,
                    path.stat().st_size,
                    str(path.resolve()),
                )
                result = self.parser.parse(source)
                self.assertTrue(result.blocks)
                self.assertTrue(any("Invoice" in (block.text or "") for block in result.blocks))
                self.assertTrue(
                    all("docling" not in type(block).__module__ for block in result.blocks)
                )
