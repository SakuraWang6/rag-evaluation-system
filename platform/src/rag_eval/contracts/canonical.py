"""RAG-neutral Canonical Data Model 1.2.

The model describes facts observed in a source document.  It deliberately has
no runtime chunk, retrieval, rank, or answer-generation fields.  The source
span coordinate system is ``ooxml-structural-v1``: ``part`` is a safe OOXML
package member; ``coordinates`` preserve the parser's direct structural
locator.  In particular, ``body_ordinal`` is zero-based among ``w:body``
children, table ``row``/``column`` are one-based logical coordinates, and an
optional ``text_start``/``text_end`` is a zero-based, end-exclusive Unicode
code-point range in that extracted object's normalized text witness.  It is
never a retrieval-chunk offset or a rendered-page coordinate.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# 1.2 is an additive evolution of the 1.0/1.1 Canonical Contract. Readers
# keep accepting frozen historical snapshots exactly as they were pinned.
CANONICAL_SCHEMA_VERSION = "1.2"
PREVIOUS_CANONICAL_SCHEMA_VERSION = "1.1"
LEGACY_CANONICAL_SCHEMA_VERSION = "1.0"
CANONICAL_CONFORMANCE_SCHEMA_VERSION = "canonical-conformance/1"
CANONICAL_GOLD_ELIGIBILITY_POLICY_IDENTITY = (
    "rag-eval-canonical-gold-eligibility/1"
)


class CanonicalContractError(ValueError):
    """A canonical document is structurally invalid or not usable as evidence."""


class CanonicalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CanonicalObjectType(StrEnum):
    DOCUMENT = "document"
    SECTION = "section"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TEXT_SPAN = "text_span"
    TABLE = "table"
    ROW = "row"
    CELL = "cell"
    LOGICAL_ROW = "logical_row"
    LOGICAL_COLUMN = "logical_column"
    LOGICAL_CELL = "logical_cell"
    FIGURE = "figure"
    CAPTION = "caption"
    EQUATION = "equation"
    REFERENCE = "reference"
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"
    EMBEDDED_OBJECT = "embedded_object"
    MEDIA_RESOURCE = "media_resource"


class RepresentationStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    MISSING = "missing"


class CanonicalRelationType(StrEnum):
    PARENT_CHILD = "parent_child"
    SIBLING = "sibling"
    SECTION_HIERARCHY = "section_hierarchy"
    DOCUMENT_ORDER = "document_order"
    CAPTION_OF = "caption_of"
    REFERENCE_TO = "reference_to"
    FIGURE_HAS_RESOURCE = "figure_has_resource"
    PARAGRAPH_REFERENCES_FIGURE = "paragraph_references_figure"
    EQUATION_IN_PARAGRAPH = "equation_in_paragraph"
    SECTION_CONTAINS_FIGURE = "section_contains_figure"
    SECTION_CONTAINS_EQUATION = "section_contains_equation"
    TABLE_CONTAINS_ROW = "table_contains_row"
    ROW_CONTAINS_CELL = "row_contains_cell"
    TABLE_CONTAINS_LOGICAL_ROW = "table_contains_logical_row"
    TABLE_CONTAINS_LOGICAL_COLUMN = "table_contains_logical_column"
    LOGICAL_ROW_CONTAINS_CELL = "logical_row_contains_cell"
    LOGICAL_COLUMN_CONTAINS_CELL = "logical_column_contains_cell"
    PHYSICAL_TO_LOGICAL_CELL = "physical_to_logical_cell"
    HEADER_FOR = "header_for"
    NESTED_TABLE_IN_CELL = "nested_table_in_cell"


class CanonicalConformanceStatus(StrEnum):
    CONFORMANT = "conformant"
    NONCONFORMANT = "nonconformant"
    NOT_EVALUATED = "not_evaluated"


class CanonicalGoldEligibilityRule(CanonicalModel):
    """One Platform-owned admission decision for a canonical subtype."""

    subtype: str = Field(min_length=1)
    object_types: tuple[CanonicalObjectType, ...] = Field(min_length=1)
    gold_evidence_eligible: bool
    rationale: str = Field(min_length=1)


class CanonicalObjectConformance(CanonicalModel):
    """Conformance and Gold eligibility for one Snapshot-local object."""

    object_id: str = Field(min_length=1)
    object_type: CanonicalObjectType
    subtype: str = Field(min_length=1)
    status: CanonicalConformanceStatus
    gold_evidence_eligible: bool
    reason_codes: tuple[str, ...] = Field(min_length=1)
    locator_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    witness_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_eligibility_requires_conformance(
        self,
    ) -> CanonicalObjectConformance:
        if (
            self.gold_evidence_eligible
            and self.status != CanonicalConformanceStatus.CONFORMANT
        ):
            raise ValueError("Gold-eligible canonical objects must be conformant")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("canonical conformance reason codes must be unique")
        return self


class CanonicalConformanceReport(CanonicalModel):
    """Immutable, adapter-independent conformance result for one Snapshot."""

    schema_version: Literal[CANONICAL_CONFORMANCE_SCHEMA_VERSION] = (
        CANONICAL_CONFORMANCE_SCHEMA_VERSION
    )
    policy_identity: Literal[CANONICAL_GOLD_ELIGIBILITY_POLICY_IDENTITY] = (
        CANONICAL_GOLD_ELIGIBILITY_POLICY_IDENTITY
    )
    canonical_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_identity: str = Field(min_length=1)
    canonicalizer_identity: str = Field(min_length=1)
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    object_results: tuple[CanonicalObjectConformance, ...] = Field(min_length=1)
    rule_matrix: tuple[CanonicalGoldEligibilityRule, ...] = Field(min_length=1)
    report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> CanonicalConformanceReport:
        object_ids = [item.object_id for item in self.object_results]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("canonical conformance report repeats object IDs")
        subtypes = [item.subtype for item in self.rule_matrix]
        if len(subtypes) != len(set(subtypes)):
            raise ValueError("canonical Gold eligibility matrix repeats subtypes")
        expected = canonical_conformance_report_digest(
            schema_version=self.schema_version,
            policy_identity=self.policy_identity,
            canonical_digest=self.canonical_digest,
            source_sha256=self.source_sha256,
            parser_identity=self.parser_identity,
            canonicalizer_identity=self.canonicalizer_identity,
            configuration_digest=self.configuration_digest,
            object_results=self.object_results,
            rule_matrix=self.rule_matrix,
        )
        if self.report_digest != expected:
            raise ValueError("canonical conformance report digest does not match")
        return self

    def result_for(self, object_id: str) -> CanonicalObjectConformance:
        for item in self.object_results:
            if item.object_id == object_id:
                return item
        raise KeyError(object_id)

    def require_gold_eligible(self, object_id: str) -> CanonicalObjectConformance:
        result = self.result_for(object_id)
        if not result.gold_evidence_eligible:
            raise CanonicalContractError(
                f"canonical object {object_id!r} is not Gold-eligible under "
                f"{self.policy_identity}: {', '.join(result.reason_codes)}"
            )
        return result

    @classmethod
    def build(
        cls,
        *,
        canonical_digest: str,
        source_sha256: str,
        parser_identity: str,
        canonicalizer_identity: str,
        configuration_digest: str,
        object_results: tuple[CanonicalObjectConformance, ...],
        rule_matrix: tuple[CanonicalGoldEligibilityRule, ...],
    ) -> CanonicalConformanceReport:
        ordered_results = tuple(sorted(object_results, key=lambda item: item.object_id))
        ordered_rules = tuple(sorted(rule_matrix, key=lambda item: item.subtype))
        digest = canonical_conformance_report_digest(
            schema_version=CANONICAL_CONFORMANCE_SCHEMA_VERSION,
            policy_identity=CANONICAL_GOLD_ELIGIBILITY_POLICY_IDENTITY,
            canonical_digest=canonical_digest,
            source_sha256=source_sha256,
            parser_identity=parser_identity,
            canonicalizer_identity=canonicalizer_identity,
            configuration_digest=configuration_digest,
            object_results=ordered_results,
            rule_matrix=ordered_rules,
        )
        return cls(
            canonical_digest=canonical_digest,
            source_sha256=source_sha256,
            parser_identity=parser_identity,
            canonicalizer_identity=canonicalizer_identity,
            configuration_digest=configuration_digest,
            object_results=ordered_results,
            rule_matrix=ordered_rules,
            report_digest=digest,
        )


class SourceSpan(CanonicalModel):
    """One directly observed source location in ``ooxml-structural-v1``."""

    coordinate_system: Literal["ooxml-structural-v1"] = "ooxml-structural-v1"
    part: str = Field(min_length=1)
    coordinates: dict[str, str | int | float | bool] = Field(min_length=1)
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_source_span(self) -> SourceSpan:
        if self.part.startswith("/") or ".." in self.part.split("/") or "\\" in self.part:
            raise ValueError("source part must be a safe OOXML package-relative path")
        if (self.text_start is None) != (self.text_end is None):
            raise ValueError("text_start and text_end must be supplied together")
        if self.text_start is not None and self.text_end is not None and self.text_end <= self.text_start:
            raise ValueError("source text span end must be greater than start")
        body_ordinal = self.coordinates.get("body_ordinal")
        if body_ordinal is not None and (
            isinstance(body_ordinal, bool)
            or not isinstance(body_ordinal, int)
            or body_ordinal < 0
        ):
            raise ValueError("body_ordinal must be a non-negative integer when supplied")
        return self


class CanonicalObjectProvenance(CanonicalModel):
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_identity: str = Field(min_length=1)
    canonicalizer_identity: str = Field(min_length=1)
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    extraction_method: str = Field(min_length=1)
    source_spans: tuple[SourceSpan, ...] = ()
    derived_from_object_ids: tuple[str, ...] = ()


class CanonicalRelationProvenance(CanonicalModel):
    extraction_method: str = Field(min_length=1)
    source_object_ids: tuple[str, ...] = Field(min_length=1)
    source_spans: tuple[SourceSpan, ...] = ()


class CanonicalObject(CanonicalModel):
    object_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    object_type: CanonicalObjectType
    representation_status: RepresentationStatus
    document_order: int = Field(ge=0)
    canonical_value: str | None = None
    provenance: CanonicalObjectProvenance
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_object_witness(self) -> CanonicalObject:
        if self.representation_status == RepresentationStatus.MISSING:
            if self.canonical_value not in (None, "") or self.provenance.source_spans:
                raise ValueError("missing canonical objects cannot claim a witness or source span")
            return self
        if not self.provenance.source_spans:
            raise ValueError("non-missing canonical objects require direct source spans")
        if self.representation_status == RepresentationStatus.COMPLETE and self.canonical_value is None:
            raise ValueError("complete canonical objects require a canonical witness")
        eligibility = self.attributes.get("gold_evidence_eligible")
        if eligibility is not None and not isinstance(eligibility, bool):
            raise ValueError("gold_evidence_eligible must be boolean when supplied")
        semantic_status = self.attributes.get("semantic_status")
        if semantic_status is not None and semantic_status not in {
            "unverified",
            "structural_only",
            "textual_context_available",
            "textually_supported",
            "human_review_required",
        }:
            raise ValueError("semantic_status is not a recognized Canonical rich-content status")
        visual_status = self.attributes.get("visual_semantic_status")
        if visual_status is not None and visual_status not in {
            "unverified",
            "not_applicable",
        }:
            raise ValueError("visual_semantic_status cannot assert unreviewed visual meaning")
        if eligibility is True and self.object_type == CanonicalObjectType.FIGURE:
            required = {
                "resource_object_id",
                "caption_object_id",
                "figure_number",
                "gold_evidence_scope",
            }
            missing = sorted(key for key in required if not self.attributes.get(key))
            if missing:
                raise ValueError(f"Gold-eligible figure lacks required auditable fields: {missing}")
            if self.attributes.get("caption_relation_status") != "reliable":
                raise ValueError("Gold-eligible figure requires a reliable caption relation")
            if self.attributes.get("reference_relation_status") != "reliable":
                raise ValueError("Gold-eligible figure requires a reliable text reference relation")
            if self.attributes.get("semantic_status") != "textually_supported":
                raise ValueError("Gold-eligible figure requires structured textual semantic support")
            if self.attributes.get("visual_semantic_status") != "unverified":
                raise ValueError("Gold-eligible figure cannot claim unverified visual semantics")
            if self.attributes.get("gold_evidence_scope") != "caption_and_text_only":
                raise ValueError("Gold-eligible figure must be restricted to caption-and-text semantics")
        if eligibility is True and self.object_type == CanonicalObjectType.EQUATION:
            required = {
                "raw_omml",
                "raw_omml_sha256",
                "omml_tree",
                "presentation_text",
                "placement",
                "paragraph_object_id",
            }
            missing = sorted(key for key in required if not self.attributes.get(key))
            if missing:
                raise ValueError(f"Gold-eligible equation lacks required auditable fields: {missing}")
            if self.attributes.get("semantic_status") != "textually_supported":
                raise ValueError("Gold-eligible equation requires structured textual semantic support")
        return self

    @property
    def gold_evidence_eligible(self) -> bool:
        """A complete object is usable unless a newer contract marks it unsafe.

        Absence preserves the semantics of immutable Canonical 1.0 snapshots;
        newer DOCX table records add an explicit false value for structures
        that are complete as physical topology but not safe formal evidence.
        """

        return (
            self.representation_status == RepresentationStatus.COMPLETE
            and self.attributes.get("gold_evidence_eligible") is not False
        )


class CanonicalRelation(CanonicalModel):
    relation_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    relation_type: CanonicalRelationType
    source_object_id: str = Field(min_length=1)
    target_object_id: str = Field(min_length=1)
    provenance: CanonicalRelationProvenance
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_distinct_endpoints(self) -> CanonicalRelation:
        if self.source_object_id == self.target_object_id:
            raise ValueError("canonical relations cannot self-reference")
        if {
            self.source_object_id,
            self.target_object_id,
        }.difference(self.provenance.source_object_ids):
            raise ValueError("relation provenance must name both relation endpoints")
        return self


class CanonicalDocumentManifest(CanonicalModel):
    schema_version: Literal[
        LEGACY_CANONICAL_SCHEMA_VERSION,
        PREVIOUS_CANONICAL_SCHEMA_VERSION,
        CANONICAL_SCHEMA_VERSION,
    ] = CANONICAL_SCHEMA_VERSION
    document_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_identity: str = Field(min_length=1)
    canonicalizer_identity: str = Field(min_length=1)
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    object_count: int = Field(ge=1)
    relation_count: int = Field(ge=0)
    objects_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    relations_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CanonicalDocument(CanonicalModel):
    manifest: CanonicalDocumentManifest
    objects: tuple[CanonicalObject, ...] = Field(min_length=1)
    relations: tuple[CanonicalRelation, ...] = ()

    @model_validator(mode="after")
    def validate_document(self) -> CanonicalDocument:
        object_ids = [item.object_id for item in self.objects]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("canonical object IDs must be unique")
        orders = [item.document_order for item in self.objects]
        if len(orders) != len(set(orders)):
            raise ValueError("canonical document_order values must be unique")
        if any(item.document_id != self.manifest.document_id for item in self.objects):
            raise ValueError("canonical object document IDs must match the manifest")
        if not any(item.object_type == CanonicalObjectType.DOCUMENT for item in self.objects):
            raise ValueError("canonical document requires one document object")
        policy_values = {
            item.attributes.get("gold_eligibility_policy") for item in self.objects
        }
        policy_values.discard(None)
        if policy_values:
            if policy_values != {CANONICAL_GOLD_ELIGIBILITY_POLICY_IDENTITY}:
                raise ValueError("canonical objects use an unknown Gold eligibility policy")
            for item in self.objects:
                if (
                    item.attributes.get("gold_eligibility_policy")
                    != CANONICAL_GOLD_ELIGIBILITY_POLICY_IDENTITY
                    or not isinstance(
                        item.attributes.get("gold_evidence_eligible"), bool
                    )
                    or not isinstance(
                        item.attributes.get("gold_eligibility_subtype"), str
                    )
                    or not item.attributes.get("gold_eligibility_reasons")
                ):
                    raise ValueError(
                        "current canonical snapshots require an explicit Gold "
                        "eligibility decision for every object"
                    )

        relation_ids = [item.relation_id for item in self.relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("canonical relation IDs must be unique")
        objects_by_id = {item.object_id: item for item in self.objects}
        if any(item.document_id != self.manifest.document_id for item in self.relations):
            raise ValueError("canonical relation document IDs must match the manifest")
        for relation in self.relations:
            if relation.source_object_id not in objects_by_id or relation.target_object_id not in objects_by_id:
                raise ValueError("canonical relation references an unknown object")
            self._validate_relation_shape(relation, objects_by_id)
        parents_by_child: dict[str, set[str]] = defaultdict(set)
        parent_edges = {
            (relation.source_object_id, relation.target_object_id)
            for relation in self.relations
            if relation.relation_type == CanonicalRelationType.PARENT_CHILD
        }
        for parent_id, child_id in parent_edges:
            parents_by_child[child_id].add(parent_id)
        for relation in self.relations:
            if relation.relation_type == CanonicalRelationType.SIBLING:
                if not parents_by_child[relation.source_object_id].intersection(
                    parents_by_child[relation.target_object_id]
                ):
                    raise ValueError("sibling relation requires a shared parent_child relation")
            if relation.relation_type == CanonicalRelationType.SECTION_HIERARCHY and (
                relation.source_object_id,
                relation.target_object_id,
            ) not in parent_edges:
                raise ValueError("section_hierarchy requires the same parent_child relation")

        expected = build_canonical_manifest(
            schema_version=self.manifest.schema_version,
            document_id=self.manifest.document_id,
            source_sha256=self.manifest.source_sha256,
            parser_identity=self.manifest.parser_identity,
            canonicalizer_identity=self.manifest.canonicalizer_identity,
            configuration_digest=self.manifest.configuration_digest,
            objects=self.objects,
            relations=self.relations,
        )
        if self.manifest != expected:
            raise ValueError("canonical document manifest digests do not match its objects and relations")
        return self

    @staticmethod
    def _validate_relation_shape(
        relation: CanonicalRelation,
        objects: dict[str, CanonicalObject],
    ) -> None:
        source = objects[relation.source_object_id]
        target = objects[relation.target_object_id]
        if relation.relation_type == CanonicalRelationType.DOCUMENT_ORDER and source.document_order >= target.document_order:
            raise ValueError("document_order relation must point from earlier to later object")
        if relation.relation_type == CanonicalRelationType.SECTION_HIERARCHY:
            if source.object_type != CanonicalObjectType.SECTION or target.object_type != CanonicalObjectType.SECTION:
                raise ValueError("section_hierarchy requires section endpoints")
        if relation.relation_type == CanonicalRelationType.TABLE_CONTAINS_ROW:
            if source.object_type != CanonicalObjectType.TABLE or target.object_type != CanonicalObjectType.ROW:
                raise ValueError("table_contains_row requires table -> row")
        if relation.relation_type == CanonicalRelationType.ROW_CONTAINS_CELL:
            if source.object_type != CanonicalObjectType.ROW or target.object_type != CanonicalObjectType.CELL:
                raise ValueError("row_contains_cell requires row -> cell")
        if relation.relation_type == CanonicalRelationType.TABLE_CONTAINS_LOGICAL_ROW:
            if source.object_type != CanonicalObjectType.TABLE or target.object_type != CanonicalObjectType.LOGICAL_ROW:
                raise ValueError("table_contains_logical_row requires table -> logical_row")
        if relation.relation_type == CanonicalRelationType.TABLE_CONTAINS_LOGICAL_COLUMN:
            if source.object_type != CanonicalObjectType.TABLE or target.object_type != CanonicalObjectType.LOGICAL_COLUMN:
                raise ValueError("table_contains_logical_column requires table -> logical_column")
        if relation.relation_type == CanonicalRelationType.LOGICAL_ROW_CONTAINS_CELL:
            if source.object_type != CanonicalObjectType.LOGICAL_ROW or target.object_type != CanonicalObjectType.LOGICAL_CELL:
                raise ValueError("logical_row_contains_cell requires logical_row -> logical_cell")
        if relation.relation_type == CanonicalRelationType.LOGICAL_COLUMN_CONTAINS_CELL:
            if source.object_type != CanonicalObjectType.LOGICAL_COLUMN or target.object_type != CanonicalObjectType.LOGICAL_CELL:
                raise ValueError("logical_column_contains_cell requires logical_column -> logical_cell")
        if relation.relation_type == CanonicalRelationType.PHYSICAL_TO_LOGICAL_CELL:
            if source.object_type != CanonicalObjectType.CELL or target.object_type != CanonicalObjectType.LOGICAL_CELL:
                raise ValueError("physical_to_logical_cell requires cell -> logical_cell")
        if relation.relation_type == CanonicalRelationType.HEADER_FOR:
            if source.object_type != CanonicalObjectType.LOGICAL_CELL or target.object_type != CanonicalObjectType.LOGICAL_CELL:
                raise ValueError("header_for requires logical_cell -> logical_cell")
        if relation.relation_type == CanonicalRelationType.NESTED_TABLE_IN_CELL:
            if source.object_type != CanonicalObjectType.CELL or target.object_type != CanonicalObjectType.TABLE:
                raise ValueError("nested_table_in_cell requires cell -> table")
        if relation.relation_type == CanonicalRelationType.CAPTION_OF:
            if source.object_type != CanonicalObjectType.CAPTION or target.object_type not in {CanonicalObjectType.FIGURE, CanonicalObjectType.TABLE}:
                raise ValueError("caption_of requires caption -> figure/table")
        if relation.relation_type == CanonicalRelationType.REFERENCE_TO and source.object_type != CanonicalObjectType.REFERENCE:
            raise ValueError("reference_to requires a reference source")
        if relation.relation_type == CanonicalRelationType.FIGURE_HAS_RESOURCE:
            if source.object_type != CanonicalObjectType.FIGURE or target.object_type != CanonicalObjectType.MEDIA_RESOURCE:
                raise ValueError("figure_has_resource requires figure -> media_resource")
        if relation.relation_type == CanonicalRelationType.PARAGRAPH_REFERENCES_FIGURE:
            if source.object_type != CanonicalObjectType.PARAGRAPH or target.object_type != CanonicalObjectType.FIGURE:
                raise ValueError("paragraph_references_figure requires paragraph -> figure")
        if relation.relation_type == CanonicalRelationType.EQUATION_IN_PARAGRAPH:
            if source.object_type != CanonicalObjectType.EQUATION or target.object_type != CanonicalObjectType.PARAGRAPH:
                raise ValueError("equation_in_paragraph requires equation -> paragraph")
        if relation.relation_type == CanonicalRelationType.SECTION_CONTAINS_FIGURE:
            if source.object_type != CanonicalObjectType.SECTION or target.object_type != CanonicalObjectType.FIGURE:
                raise ValueError("section_contains_figure requires section -> figure")
        if relation.relation_type == CanonicalRelationType.SECTION_CONTAINS_EQUATION:
            if source.object_type != CanonicalObjectType.SECTION or target.object_type != CanonicalObjectType.EQUATION:
                raise ValueError("section_contains_equation requires section -> equation")

    def object_by_id(self, object_id: str) -> CanonicalObject:
        for item in self.objects:
            if item.object_id == object_id:
                return item
        raise KeyError(object_id)

    def require_complete_object(self, object_id: str) -> CanonicalObject:
        """Return usable evidence or fail closed for partial/unsupported/missing data."""

        item = self.object_by_id(object_id)
        if item.representation_status != RepresentationStatus.COMPLETE:
            raise CanonicalContractError(
                f"canonical object {object_id!r} is {item.representation_status}; complete evidence is required"
            )
        if not item.gold_evidence_eligible:
            raise CanonicalContractError(
                f"canonical object {object_id!r} is structurally complete but prohibited as Gold evidence"
            )
        return item

    @classmethod
    def build(
        cls,
        *,
        document_id: str,
        source_sha256: str,
        parser_identity: str,
        canonicalizer_identity: str,
        configuration_digest: str,
        objects: tuple[CanonicalObject, ...],
        relations: tuple[CanonicalRelation, ...],
    ) -> CanonicalDocument:
        manifest = build_canonical_manifest(
            document_id=document_id,
            source_sha256=source_sha256,
            parser_identity=parser_identity,
            canonicalizer_identity=canonicalizer_identity,
            configuration_digest=configuration_digest,
            objects=objects,
            relations=relations,
        )
        return cls(manifest=manifest, objects=objects, relations=relations)


def canonical_json(value: object) -> str:
    """Stable JSON representation used by every contract digest."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def records_digest(values: tuple[CanonicalObject, ...] | tuple[CanonicalRelation, ...]) -> str:
    key = "object_id" if values and isinstance(values[0], CanonicalObject) else "relation_id"
    payload = "".join(
        canonical_json(value) + "\n"
        for value in sorted(values, key=lambda item: str(getattr(item, key)))
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_conformance_report_digest(
    *,
    schema_version: str,
    policy_identity: str,
    canonical_digest: str,
    source_sha256: str,
    parser_identity: str,
    canonicalizer_identity: str,
    configuration_digest: str,
    object_results: tuple[CanonicalObjectConformance, ...],
    rule_matrix: tuple[CanonicalGoldEligibilityRule, ...],
) -> str:
    payload = {
        "schema_version": schema_version,
        "policy_identity": policy_identity,
        "canonical_digest": canonical_digest,
        "source_sha256": source_sha256,
        "parser_identity": parser_identity,
        "canonicalizer_identity": canonicalizer_identity,
        "configuration_digest": configuration_digest,
        "object_results": [
            item.model_dump(mode="json", exclude_none=True)
            for item in sorted(object_results, key=lambda value: value.object_id)
        ],
        "rule_matrix": [
            item.model_dump(mode="json")
            for item in sorted(rule_matrix, key=lambda value: value.subtype)
        ],
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def build_canonical_manifest(
    *,
    schema_version: Literal[
        LEGACY_CANONICAL_SCHEMA_VERSION,
        PREVIOUS_CANONICAL_SCHEMA_VERSION,
        CANONICAL_SCHEMA_VERSION,
    ] = CANONICAL_SCHEMA_VERSION,
    document_id: str,
    source_sha256: str,
    parser_identity: str,
    canonicalizer_identity: str,
    configuration_digest: str,
    objects: tuple[CanonicalObject, ...],
    relations: tuple[CanonicalRelation, ...],
) -> CanonicalDocumentManifest:
    objects_digest = records_digest(objects)
    relations_digest = records_digest(relations)
    payload = {
        "schema_version": schema_version,
        "document_id": document_id,
        "source_sha256": source_sha256,
        "parser_identity": parser_identity,
        "canonicalizer_identity": canonicalizer_identity,
        "configuration_digest": configuration_digest,
        "object_count": len(objects),
        "relation_count": len(relations),
        "objects_digest": objects_digest,
        "relations_digest": relations_digest,
    }
    return CanonicalDocumentManifest(
        **payload,
        canonical_digest=hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
    )
