from __future__ import annotations

import sys
import unittest
from pathlib import Path


from app_accounting_batch.workflow import InvoiceBatchWorkflow
from core_shared.domain import (
    ContentBlock,
    DocumentClassification,
    DocumentType,
    ExtractionResult,
    FileReference,
    ParsedDocument,
)


class InvoiceClassifier:
    def classify(self, source, parsed=None):
        return DocumentClassification(DocumentType.INVOICE, 0.99, "test-rules")


class TextParser:
    def supported_media_types(self):
        return ("application/pdf",)

    def parse(self, source):
        return ParsedDocument(source, (ContentBlock("1", "text", "Total: 100"),), "fake")


class InvoiceExtractor:
    def extract(self, document, *, schema_name, schema_version, schema):
        return ExtractionResult(
            document.source.file_id,
            schema_name,
            schema_version,
            {"total": 100},
            "fake",
        )


class InvoiceBatchWorkflowTest(unittest.TestCase):
    def test_processes_invoice_through_neutral_ports(self):
        source = FileReference(
            "file-1",
            "workspace-1",
            "invoice.pdf",
            "application/pdf",
            123,
            "object://workspace-1/file-1",
        )
        workflow = InvoiceBatchWorkflow(
            classifier=InvoiceClassifier(),
            parser=TextParser(),
            extractor=InvoiceExtractor(),
        )

        result = workflow.process(
            [source],
            schema={"type": "object"},
            schema_version="1.0",
        )

        self.assertEqual(result[0].extraction.values["total"], 100)
        self.assertEqual(result[0].errors, ())


if __name__ == "__main__":
    unittest.main()
