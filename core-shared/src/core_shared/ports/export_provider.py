from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from core_shared.domain import ExportArtifact


class ExportProvider(Protocol):
    """Export approved, application-owned records to a file artifact."""

    def export(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> ExportArtifact: ...
