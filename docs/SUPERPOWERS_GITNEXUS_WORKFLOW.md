# Superpowers & GitNexus Development Workflow

This document defines the software engineering methodology, architectural discipline, and AI Agent operational rules for the **File-First AI Workspace** project.

All AI coding assistants (including Antigravity, Claude Code, and autonomous agents) working on this repository must strictly adhere to the practices described here.

---

## 1. Core Principles

1. **Architecture Enforcement via GitNexus (Codebase Graph Intelligence)**
   - Every modification must respect the **Clean / Hexagonal Architecture** boundaries (`domain` $\rightarrow$ `ports` $\rightarrow$ `adapters` $\rightarrow$ `application`).
   - **Zero Vendor Creep in Core**: The `domain/` and `ports/` modules must remain 100% provider-neutral. No vendor SDKs (e.g., OpenAI, Google GenAI, LangChain, Docling, PyTorch) may be imported into domain models or port interfaces.
   - **Architectural Traceability**: Before adding or refactoring code, trace call chains and symbol dependencies across the ports and adapters to prevent architectural drift.

2. **Disciplined Agent Execution via Superpowers**
   - **No Blind Coding / AI-Slop**: Never write implementation code without an explicit design contract, schema definition, and test strategy.
   - **Test-Driven Development (TDD)**: Write or update unit test fixtures (`pytest`) alongside or prior to implementing adapters and workflows.
   - **Incremental Building & Empirical Verification**: Implement changes in small, discrete steps. Run verification commands (`pytest`, build scripts) after every edit and fix errors immediately based on log tracebacks.
   - **License & Commercial Safety Gate**: No third-party package or pre-trained model may enter production without license review and recording in `docs/REPO_MAP.md`.

---

## 2. Five-Phase Workflow Specification

```text
[Phase 1: Design & Schema First]
              │
              ▼
[Phase 2: TDD & Test Contracts]
              │
              ▼
[Phase 3: Incremental Adapter Build]
              │
              ▼
[Phase 4: License & Security Gate]
              │
              ▼
[Phase 5: Verification & Quality Gate]
```

### Phase 1: Design & Schema First
- Define versioned target JSON schemas (e.g., invoice fields, line items, supplier metadata).
- Specify domain models in `domain/models.py` and interface contracts in `ports/`.
- Ensure all fields include clear descriptions and validation constraints.

### Phase 2: Test-Driven Development (TDD)
- Create test files under `backend/tests/` targeting the new ports or adapters.
- Use mock responses or sample fixtures to verify expected behavior, error handling, and batch isolation.
- Ensure tests cover both happy paths and edge cases (e.g., corrupt files, missing fields, rate limits).

### Phase 3: Incremental Adapter Building
- Implement adapters in `adapters/` implementing the corresponding `ports/` interfaces.
- Translate external vendor objects into neutral domain objects inside the adapter boundary.
- Isolate engine-specific logic so adapters can be swapped through configuration and dependency injection without touching application workflows.

### Phase 4: License & Security Gate
- Verify all dependencies and model licenses against commercial standards (MIT, Apache-2.0, BSD, CDLA-Permissive).
- Log dependency metadata, model weights revisions, and usage boundaries in `docs/REPO_MAP.md`.

### Phase 5: Verification & Quality Gate
- Run automated test suites: `pytest` in `backend/`.
- Confirm 100% clean passes without swallowing exceptions or masking errors.
- Document changes in `walkthrough.md` or implementation logs.

---

## 3. GitNexus Architecture Boundaries Matrix

| Layer | Permitted Imports | Prohibited Imports | Purpose |
| :--- | :--- | :--- | :--- |
| **`domain/`** | Python stdlib (`dataclasses`, `typing`, `datetime`, `enum`) | Vendor SDKs, Web Frameworks, DB ORMs, Adapters, Ports | Pure business entities and domain rules. |
| **`ports/`** | `domain/`, Python stdlib | Vendor SDKs, Concrete Adapters, Web Frameworks | Abstract interface contracts owned by the application. |
| **`application/`** | `domain/`, `ports/`, Python stdlib | Vendor SDKs, Concrete Adapters, Web Frameworks | Workflow orchestrators (e.g., `InvoiceBatchWorkflow`). |
| **`adapters/`** | `domain/`, `ports/`, Vendor SDKs (OpenAI, Docling, etc.) | Web Frameworks, Database ORMs | Implementation of ports using external libraries. |
| **`delivery/`** | `application/`, `adapters/`, FastAPI/Web frameworks | Direct mutation of private domain state | HTTP endpoints, background workers, CLI commands. |

---

## 4. Agent Guidelines Summary

* **Check before edit**: Verify symbol definitions and call chains before modifying functions or classes.
* **Keep errors visible**: Never wrap broken calls in silent `try/except` blocks or return empty dummy fallbacks.
* **Empirical proof required**: Every code modification must be verified by running `pytest`.
