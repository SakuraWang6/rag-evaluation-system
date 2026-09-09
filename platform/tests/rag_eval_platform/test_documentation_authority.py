from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ARCHITECTURE_DOCUMENTS = {
    "ARTIFACT_V2_PRESENTATION.md",
    "CANONICAL_CONFORMANCE.md",
    "CURRENT_ARCHITECTURE.md",
    "LIGHTRAG_NATIVE_OBSERVATION.md",
    "RAG_ANYTHING_NATIVE_OBSERVATION.md",
    "README.md",
    "RUN_ARTIFACT_V2.md",
    "UNIFIED_EVALUATION_V2.md",
    "UNIFIED_OBSERVATION_CONTRACT.md",
}
DECISION_DOCUMENTS = {
    "0001-runtime-evidence-cardinality-and-prompt-trace.md",
    "0002-architecture-change-envelope.md",
    "0003-native-document-evaluation-v2.md",
    "0004-native-v2-only-convergence.md",
}
PLATFORM_GUIDES = {"BENCHMARK_AUTHORING.md", "QUICK_START.md"}
ENTRY_DOCUMENTS = {
    Path("README.md"),
    Path("platform/README.md"),
    Path("adapters/README.md"),
    Path("adapters/lightrag/README.md"),
    Path("adapters/rag-anything/README.md"),
    Path("webui/README.md"),
}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _relative_markdown_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.md")
        if path.is_file()
    }


def _maintained_documents() -> tuple[Path, ...]:
    paths = set(ENTRY_DOCUMENTS)
    paths.update(Path("docs/architecture") / name for name in ARCHITECTURE_DOCUMENTS)
    paths.update(Path("docs/decisions") / name for name in DECISION_DOCUMENTS)
    paths.update(Path("platform/docs") / name for name in PLATFORM_GUIDES)
    return tuple(
        REPOSITORY_ROOT / path
        for path in sorted(paths, key=lambda candidate: candidate.as_posix())
    )


def test_long_term_documentation_has_one_native_v2_authority() -> None:
    assert _relative_markdown_files(REPOSITORY_ROOT / "docs/architecture") == (
        ARCHITECTURE_DOCUMENTS
    )
    assert _relative_markdown_files(REPOSITORY_ROOT / "docs/decisions") == (
        DECISION_DOCUMENTS
    )
    assert _relative_markdown_files(REPOSITORY_ROOT / "platform/docs") == (
        PLATFORM_GUIDES
    )
    assert {
        path.name for path in (REPOSITORY_ROOT / "platform").glob("*.md")
    } == {"README.md"}
    for retired_directory in (
        "docs/audit",
        "docs/migration",
        "platform/docs/archive",
        "platform/docs/evidence-repair",
        "webui/docs",
    ):
        assert _relative_markdown_files(REPOSITORY_ROOT / retired_directory) == set()

    current_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in _maintained_documents()
        if "docs/decisions" not in path.as_posix()
    )
    for stale_claim in (
        "Wire 1.0 remains",
        "Artifact 1.2 remains",
        "compatibility window",
        "native_v2_characterization",
        "shadow scorer",
        "shadow observation",
        "RAGResult.trace.wire_v2_native_observation",
        "historical Replay",
        "/Users/",
    ):
        assert stale_claim not in current_text

    architecture = (
        REPOSITORY_ROOT / "docs/architecture/CURRENT_ARCHITECTURE.md"
    ).read_text(encoding="utf-8")
    assert "Original DOCX" in architecture
    assert "ResolvedRunPlanV2" in architecture
    assert "RunRecordV2" in architecture
    assert "Artifact 2.0" in architecture
    assert "AdapterRunResultV2" in architecture


def test_maintained_documentation_links_are_portable_and_resolve() -> None:
    failures: list[str] = []
    for path in _maintained_documents():
        for target in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            target_path = target.split("#", maxsplit=1)[0]
            if not target_path:
                continue
            if target_path.startswith("/"):
                failures.append(f"{path.relative_to(REPOSITORY_ROOT)}: absolute {target}")
                continue
            resolved = (path.parent / target_path).resolve()
            if not resolved.is_relative_to(REPOSITORY_ROOT) or not resolved.exists():
                failures.append(f"{path.relative_to(REPOSITORY_ROOT)}: missing {target}")
    assert failures == []
