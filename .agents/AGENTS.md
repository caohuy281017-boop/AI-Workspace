# Workspace Agent Rules: Superpowers & GitNexus Workflow

All AI Coding Agents working in this repository must follow the rules defined below and detailed in [docs/SUPERPOWERS_GITNEXUS_WORKFLOW.md](file:///d:/AI-Workspace-20260808T135906Z-1-001/AI-Workspace/docs/SUPERPOWERS_GITNEXUS_WORKFLOW.md).

## 1. Architectural Boundaries (GitNexus Enforcement)
- Keep `file_first_ai/domain` and `file_first_ai/ports` 100% vendor-neutral.
- Do NOT import third-party SDKs (OpenAI, LangChain, Docling, PyTorch, etc.) inside `domain` or `ports`.
- Put all vendor-specific code strictly inside `file_first_ai/adapters/`.

## 2. Superpowers Development Discipline
- **Design & Schema First**: Define data schemas and domain/port contracts before writing adapter code.
- **TDD First**: Create or update unit test fixtures (`backend/tests/`) alongside or prior to writing adapter logic.
- **Incremental Edits**: Make discrete changes and verify using `pytest` after every edit.
- **No Masking Errors**: Diagnose root causes from log tracebacks; do not swallow exceptions or comment out tests.
- **Commercial Safety**: Record any new dependency or model license in `docs/REPO_MAP.md`.
