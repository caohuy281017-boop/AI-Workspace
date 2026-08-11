# File-First AI Workspace — Product

## Product vision

File-First AI Workspace is a commercial SaaS that turns business files into useful, reviewable outputs. A user begins with one or more files—not a blank chat. The platform identifies each document, selects an appropriate workflow, runs specialized processing, and returns structured data or a new document.

The product should make document automation approachable to business users while preserving traceability: users can see the source file, inspect extracted or generated content, correct mistakes, and export the result.

## Product principles

- **File first:** files, batches, derived artifacts, and processing jobs are first-class objects.
- **Human review before trust:** consequential outputs are reviewable and editable before export.
- **Traceable results:** extracted values should retain source/page references and confidence where an engine provides them.
- **Replaceable engines:** product behavior belongs to our application; parsers, OCR systems, and AI providers are replaceable capabilities.
- **Privacy by design:** minimize retention, isolate tenant data, encrypt files, and make deletion behavior explicit.
- **Commercially safe:** no third-party code or model enters production before license review is recorded.
- **Simple first:** build the invoice batch path before a general workflow platform.

## Initial applications

### 1. Invoice Intelligence (Kho Chứng Từ AI)

**Định vị:** Đọc, tra cứu và chuẩn bị dữ liệu hóa đơn để xuất sang phần mềm kế toán hiện có. Không thay thế phần mềm kế toán.

Input: multiple invoice PDFs or images.

Planned flow:

1. Upload a folder or select multiple files.
2. Detect file type and classify invoice-like documents.
3. Parse embedded text or use OCR / Vision AI when needed.
4. Extract invoice fields (Buyer, Supplier, Tax IDs, Amounts, etc.) into a stable schema (Schema v2).
5. Show a fast search/filter interface and a review table with validation warnings and source evidence.
6. Let users edit, verify, and export an XLSX workbook ready for MISA, FAST, or ERPs.

Initial fields should include supplier, invoice number, invoice date, currency, subtotal, tax, total, and line items. The schema will be versioned before implementation.

### 2. Document Translator (Sắp ra mắt)

Input: PDF, DOCX, or PPTX.

Output: a translated document, preserving structure and layout as far as the selected format and engine permit. The workflow should retain headings, paragraphs, tables, slides, images, and reading order where possible, and clearly flag layout degradation.

### 3. Meeting Notes (Sắp ra mắt)

Input: MP3 or MP4.

Output: transcript, speaker segments when available, summary, action items, and a DOCX report. Speaker labels and action items must remain editable.

## First functional milestone

The first end-to-end milestone is:

> Folder of invoice PDFs/images → structured JSON → review table → XLSX.

### In scope

- Batch upload and per-file processing status.
- PDF/image type detection.
- One parser/OCR/extraction implementation behind internal interfaces.
- Versioned invoice JSON schema.
- Review and correction of extracted fields.
- XLSX export.
- Failure reporting and retry at file level.
- Source evidence and confidence when available.

### Out of scope

- Full bookkeeping or tax filing.
- Bank reconciliation.
- A generic no-code workflow builder.
- Multiple engines for every capability.
- Automatic approval without human review.
- Translation and meeting workflows in the first milestone.

## Primary users

- Small finance and operations teams processing invoice batches.
- Accountants and bookkeepers preparing spreadsheet imports.
- Teams translating business documents.
- Teams turning recorded meetings into accountable notes.

## Core product objects

- **Workspace:** tenant boundary for users, files, and configuration.
- **File:** immutable uploaded source plus metadata and checksum.
- **Batch:** an ordered collection of files processed together.
- **Job:** execution state, selected workflow, attempts, and errors.
- **Artifact:** parsed document, JSON result, transcript, translated file, or export.
- **Review:** user edits, validation state, and approval history.

## Success criteria for the first milestone

- A user can process a mixed batch without one bad file failing the entire batch.
- Every output row maps back to a source file.
- Users can correct values before export.
- JSON and XLSX represent the approved values consistently.
- Engine-specific code remains outside the core application.
- All production dependencies and models have a recorded license decision.

## Open product decisions

- Target countries and invoice/tax schemas for the first release.
- Maximum batch/file size and retention defaults.
- Required confidence thresholds and validation rules.
- Whether original files are retained after export by default.
- XLSX template and downstream accounting-system compatibility.
