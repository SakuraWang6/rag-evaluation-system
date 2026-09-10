"""Crash-safe immutable publication and scorer-free reading of Artifact 2.0."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from rag_eval.artifact_contract import canonical_artifact_bytes
from rag_eval.contracts.observation import (
    ObservationProfileIdentity,
    RuntimeProfileIdentity,
)
from rag_eval.runs.eligibility import build_artifact_summary, build_case_index
from rag_eval.runs.models import (
    ARTIFACT_V2_DIRECTORY,
    ARTIFACT_V2_MANIFEST,
    ArtifactCaseIndexV2,
    ArtifactCaseReferenceV2,
    ArtifactChecksumGraphV2,
    ArtifactMemberV2,
    BenchmarkIdentityV2,
    RunArtifactCaseV2,
    RunArtifactManifestV2,
    RunArtifactSummaryV2,
    case_artifact_path,
)
from rag_eval.storage.atomic import atomic_write_bytes


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_model(path: Path, model) -> str:
    payload = canonical_artifact_bytes(model)
    atomic_write_bytes(path, payload)
    return _sha256_bytes(payload)


def _directory_hashes(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    return {
        path.relative_to(root).as_posix(): _sha256_bytes(path.read_bytes())
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def _profile_identities(
    cases: tuple[RunArtifactCaseV2, ...],
) -> tuple[
    tuple[RuntimeProfileIdentity, ...],
    tuple[ObservationProfileIdentity, ...],
]:
    runtime_profiles: dict[tuple[str, str], RuntimeProfileIdentity] = {}
    observation_profiles: dict[str, ObservationProfileIdentity] = {}
    for case in cases:
        if case.adapter_result is None:
            continue
        runtime = case.adapter_result.trace.runtime_profile
        runtime_key = (runtime.profile_id, runtime.configuration_digest)
        previous_runtime = runtime_profiles.setdefault(runtime_key, runtime)
        if previous_runtime != runtime:
            raise ValueError(
                "Artifact cases conflict on a RAG runtime profile identity"
            )
        observation = case.adapter_result.trace.observation_profile
        previous_observation = observation_profiles.setdefault(
            observation.profile_digest, observation
        )
        if previous_observation != observation:
            raise ValueError(
                "Artifact cases conflict on an Adapter observation profile identity"
            )
    return (
        tuple(runtime_profiles[key] for key in sorted(runtime_profiles)),
        tuple(observation_profiles[key] for key in sorted(observation_profiles)),
    )


@dataclass(frozen=True, slots=True)
class ArtifactV2Verification:
    valid: bool
    missing: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()
    mismatched: tuple[str, ...] = ()
    invalid_models: tuple[str, ...] = ()


class ArtifactWriter:
    """Publish one immutable, self-contained Artifact 2.0 directory."""

    def __init__(self, run_directory: Path) -> None:
        self.run_directory = run_directory

    @property
    def destination(self) -> Path:
        return self.run_directory / ARTIFACT_V2_DIRECTORY

    def publish(
        self,
        *,
        run_id: str,
        experiment_id: str,
        benchmark_identity: BenchmarkIdentityV2,
        cases: tuple[RunArtifactCaseV2, ...],
        started_at: datetime,
        completed_at: datetime,
    ) -> RunArtifactManifestV2:
        if not cases:
            raise ValueError("Artifact 2.0 requires at least one case execution")
        keys = [(item.case_id, item.repetition) for item in cases]
        if len(keys) != len(set(keys)):
            raise ValueError("Artifact 2.0 repeats a case execution")
        self.run_directory.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=".artifact-v2.", dir=self.run_directory)
        )
        try:
            manifest = self._stage(
                staging,
                run_id=run_id,
                experiment_id=experiment_id,
                benchmark_identity=benchmark_identity,
                cases=cases,
                started_at=started_at,
                completed_at=completed_at,
            )
            verification = ArtifactV2Reader(staging).verify()
            if not verification.valid:
                raise ValueError(
                    "staged Artifact 2.0 failed self-verification: "
                    f"{verification}"
                )
            if self.destination.exists():
                if _directory_hashes(self.destination) == _directory_hashes(staging):
                    return ArtifactV2Reader(self.destination).manifest()
                raise FileExistsError(
                    f"immutable Artifact 2.0 already exists: {self.destination}"
                )
            staging.replace(self.destination)
            return manifest
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def _stage(
        self,
        root: Path,
        *,
        run_id: str,
        experiment_id: str,
        benchmark_identity: BenchmarkIdentityV2,
        cases: tuple[RunArtifactCaseV2, ...],
        started_at: datetime,
        completed_at: datetime,
    ) -> RunArtifactManifestV2:
        ordered = tuple(
            sorted(cases, key=lambda item: (item.repetition, item.case_id))
        )
        case_nodes: list[ArtifactMemberV2] = []
        case_references: list[ArtifactCaseReferenceV2] = []
        for case in ordered:
            relative = case_artifact_path(case.case_id, case.repetition)
            digest = _write_model(root / relative, case)
            member_id = f"case:{case.repetition}:{case.case_id}"
            case_nodes.append(
                ArtifactMemberV2(
                    member_id=member_id,
                    path=relative,
                    sha256=digest,
                )
            )
            case_references.append(
                ArtifactCaseReferenceV2(
                    case_id=case.case_id,
                    repetition=case.repetition,
                    path=relative,
                    sha256=digest,
                )
            )
        dependencies = tuple(item.member_id for item in case_nodes)
        index = build_case_index(ordered)
        summary = build_artifact_summary(ordered)
        index_digest = _write_model(root / "case-index.json", index)
        summary_digest = _write_model(root / "summary.json", summary)
        graph = ArtifactChecksumGraphV2.build(
            tuple(case_nodes)
            + (
                ArtifactMemberV2(
                    member_id="case-index",
                    path="case-index.json",
                    sha256=index_digest,
                    depends_on=dependencies,
                ),
                ArtifactMemberV2(
                    member_id="summary",
                    path="summary.json",
                    sha256=summary_digest,
                    depends_on=dependencies,
                ),
            )
        )
        runtime_profiles, observation_profiles = _profile_identities(ordered)
        manifest = RunArtifactManifestV2.build(
            run_id=run_id,
            experiment_id=experiment_id,
            benchmark_identity=benchmark_identity,
            runtime_profiles=runtime_profiles,
            observation_profiles=observation_profiles,
            cases=tuple(case_references),
            checksum_graph=graph,
            started_at=started_at,
            completed_at=completed_at,
        )
        _write_model(root / ARTIFACT_V2_MANIFEST, manifest)
        return manifest


class ArtifactV2Reader:
    """Read persisted v2 views without invoking runtime, mapping, or scoring."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def manifest(self) -> RunArtifactManifestV2:
        return RunArtifactManifestV2.model_validate_json(
            (self.root / ARTIFACT_V2_MANIFEST).read_text(encoding="utf-8")
        )

    def cases(self) -> tuple[RunArtifactCaseV2, ...]:
        manifest = self.manifest()
        return tuple(self._case_reference(item.path) for item in manifest.cases)

    def case(
        self, case_id: str, *, repetition: int = 1
    ) -> RunArtifactCaseV2:
        manifest = self.manifest()
        reference = next(
            (
                item
                for item in manifest.cases
                if item.case_id == case_id and item.repetition == repetition
            ),
            None,
        )
        if reference is None:
            raise FileNotFoundError(case_id)
        return self._case_reference(reference.path)

    def case_index(self) -> ArtifactCaseIndexV2:
        return ArtifactCaseIndexV2.model_validate_json(
            (self.root / "case-index.json").read_text(encoding="utf-8")
        )

    def summary(self) -> RunArtifactSummaryV2:
        return RunArtifactSummaryV2.model_validate_json(
            (self.root / "summary.json").read_text(encoding="utf-8")
        )

    def verify(self) -> ArtifactV2Verification:
        invalid_models: list[str] = []
        try:
            manifest = self.manifest()
        except (OSError, ValueError, ValidationError, json.JSONDecodeError):
            return ArtifactV2Verification(
                valid=False,
                missing=(ARTIFACT_V2_MANIFEST,)
                if not (self.root / ARTIFACT_V2_MANIFEST).is_file()
                else (),
                invalid_models=(ARTIFACT_V2_MANIFEST,),
            )
        expected = {
            item.path: item.sha256 for item in manifest.checksum_graph.nodes
        }
        actual_all = _directory_hashes(self.root)
        actual = {
            path: digest
            for path, digest in actual_all.items()
            if path != ARTIFACT_V2_MANIFEST
        }
        missing = tuple(sorted(set(expected) - set(actual)))
        unexpected = tuple(sorted(set(actual) - set(expected)))
        mismatched = tuple(
            sorted(
                path
                for path in set(expected).intersection(actual)
                if expected[path] != actual[path]
            )
        )
        for reference in manifest.cases:
            try:
                self._case_reference(reference.path)
            except (OSError, ValueError, ValidationError, json.JSONDecodeError):
                invalid_models.append(reference.path)
        try:
            cases = self.cases()
            summary = self.summary()
            index = self.case_index()
            snapshots = {}
            for case in cases:
                snapshot = case.benchmark_case
                previous = snapshots.setdefault(case.case_id, snapshot)
                if previous != snapshot:
                    invalid_models.append(ARTIFACT_V2_MANIFEST)
                if (
                    snapshot.gold.source_identity
                    != manifest.benchmark_identity.source_identity
                ):
                    invalid_models.append(reference.path)
            if set(snapshots) != {item.case_id for item in manifest.cases}:
                invalid_models.append(ARTIFACT_V2_MANIFEST)
            expected_runtime_profiles, expected_observation_profiles = (
                _profile_identities(cases)
            )
            if expected_runtime_profiles != manifest.runtime_profiles:
                invalid_models.append(ARTIFACT_V2_MANIFEST)
            if expected_observation_profiles != manifest.observation_profiles:
                invalid_models.append(ARTIFACT_V2_MANIFEST)
            if summary != build_artifact_summary(cases):
                invalid_models.append("summary.json")
            if index != build_case_index(cases):
                invalid_models.append("case-index.json")
        except (OSError, ValueError, ValidationError, json.JSONDecodeError):
            invalid_models.extend(("summary.json", "case-index.json"))
        invalid = tuple(sorted(set(invalid_models)))
        return ArtifactV2Verification(
            valid=not missing and not unexpected and not mismatched and not invalid,
            missing=missing,
            unexpected=unexpected,
            mismatched=mismatched,
            invalid_models=invalid,
        )

    def _case_reference(self, relative: str) -> RunArtifactCaseV2:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("unsafe Artifact 2.0 case reference")
        return RunArtifactCaseV2.model_validate_json(
            (self.root / path).read_text(encoding="utf-8")
        )


__all__ = [
    "ArtifactV2Reader",
    "ArtifactV2Verification",
    "ArtifactWriter",
]
