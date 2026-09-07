"""External immutable registry metadata for Dataset Bundles.

Registry records classify a Bundle without changing any file inside that Bundle.
They are intentionally separate from the Bundle Store so an historic/private
Bundle can be declared development-only without rewriting its content address.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.storage.atomic import atomic_write_json


DATASET_REGISTRY_SCHEMA_VERSION = "1.0"
FROZEN_20_CASE_BUNDLE_ID = "d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e"


class DatasetRegistryError(ValueError):
    """A registry record would mutate an immutable Bundle classification."""


class DatasetLifecycle(StrEnum):
    DRAFT = "draft"
    FROZEN = "frozen"
    RETIRED = "retired"


class DatasetUsage(StrEnum):
    DEVELOPMENT_REFERENCE_DIAGNOSTIC = "development/reference_diagnostic"
    HELD_OUT_VALIDATION = "held_out_validation"
    REGRESSION_FIXTURE = "regression_fixture"


class DatasetRegistryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_schema_version: str = DATASET_REGISTRY_SCHEMA_VERSION
    bundle_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle: DatasetLifecycle
    usage: DatasetUsage
    held_out: bool
    generalization_claim_allowed: bool
    record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata: dict[str, str | int | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_classification(self) -> DatasetRegistryRecord:
        if self.usage == DatasetUsage.DEVELOPMENT_REFERENCE_DIAGNOSTIC:
            if self.held_out or self.generalization_claim_allowed:
                raise ValueError("development/reference_diagnostic cannot be held-out or support generalization claims")
        if self.usage == DatasetUsage.HELD_OUT_VALIDATION and not self.held_out:
            raise ValueError("held_out_validation must set held_out=true")
        expected = self._digest_payload(
            registry_schema_version=self.registry_schema_version,
            bundle_id=self.bundle_id,
            lifecycle=self.lifecycle,
            usage=self.usage,
            held_out=self.held_out,
            generalization_claim_allowed=self.generalization_claim_allowed,
            metadata=self.metadata,
        )
        if self.record_digest != expected:
            raise ValueError("dataset registry record digest does not match metadata")
        return self

    @classmethod
    def build(
        cls,
        *,
        bundle_id: str,
        lifecycle: DatasetLifecycle,
        usage: DatasetUsage,
        held_out: bool,
        generalization_claim_allowed: bool,
        metadata: dict[str, str | int | bool] | None = None,
    ) -> DatasetRegistryRecord:
        values = {
            "registry_schema_version": DATASET_REGISTRY_SCHEMA_VERSION,
            "bundle_id": bundle_id,
            "lifecycle": lifecycle,
            "usage": usage,
            "held_out": held_out,
            "generalization_claim_allowed": generalization_claim_allowed,
            "metadata": metadata or {},
        }
        return cls(**values, record_digest=cls._digest_payload(**values))

    @staticmethod
    def _digest_payload(**values: object) -> str:
        encoded = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


FROZEN_20_CASE_REFERENCE = DatasetRegistryRecord.build(
    bundle_id=FROZEN_20_CASE_BUNDLE_ID,
    lifecycle=DatasetLifecycle.FROZEN,
    usage=DatasetUsage.DEVELOPMENT_REFERENCE_DIAGNOSTIC,
    held_out=False,
    generalization_claim_allowed=False,
    metadata={
        "case_count": 20,
        "classification_source": "benchmark-data-layer-p0",
        "bundle_mutated": False,
        "recorded_date": "2026-08-29",
    },
)


class DatasetRegistry:
    """Append-only external classification store keyed by immutable Bundle ID."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def register(self, record: DatasetRegistryRecord) -> DatasetRegistryRecord:
        path = self._path(record.bundle_id)
        if path.exists():
            existing = DatasetRegistryRecord.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != record:
                raise DatasetRegistryError(f"registry record for {record.bundle_id} is immutable")
            return existing
        atomic_write_json(path, record.model_dump(mode="json"))
        return record

    def bootstrap_reference_datasets(self) -> DatasetRegistryRecord:
        return self.register(FROZEN_20_CASE_REFERENCE)

    def get(self, bundle_id: str) -> DatasetRegistryRecord:
        return DatasetRegistryRecord.model_validate_json(self._path(bundle_id).read_text(encoding="utf-8"))

    def list(self) -> list[DatasetRegistryRecord]:
        return [
            DatasetRegistryRecord.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("*.json"))
        ]

    def _path(self, bundle_id: str) -> Path:
        if len(bundle_id) != 64 or any(character not in "0123456789abcdef" for character in bundle_id):
            raise DatasetRegistryError("bundle ID must be a lowercase SHA-256 digest")
        return self.root / f"{bundle_id}.json"
