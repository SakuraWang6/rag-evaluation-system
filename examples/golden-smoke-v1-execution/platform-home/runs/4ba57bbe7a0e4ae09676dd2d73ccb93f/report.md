# RAG Evaluation Run 4ba57bbe7a0e4ae09676dd2d73ccb93f

- Status: `completed`
- Dataset bundle: `bbfbb1d2761b714a595ae072f786bd527fdff5c85ba7c57c40b6d8087072ba1e`
- Adapter: `lightrag` `0.1.0`
- System: `lightrag` `1.5.5`
- Case selection: `13f6f5189d871197cf4ecf0d43c739010bdc633820200ce9013425c80ff7c9fa`
- Repetitions: `1`
- Repetition seeds: `[20260824]`
- Replay of: `None`

## Metrics

```json
{
  "metrics": {
    "answer_accuracy": {
      "status": "observed",
      "value": 0.0,
      "mean": 0.0,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.0
      ],
      "numerator": 0.0,
      "denominator": 8,
      "errors": 0,
      "coverage": 0.3333333333333333,
      "status_counts": {
        "observed": 8,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 16
      }
    },
    "answer_groundedness": {
      "status": "observed",
      "value": 0.0,
      "mean": 0.0,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.0
      ],
      "numerator": 0.0,
      "denominator": 8,
      "errors": 0,
      "coverage": 0.3333333333333333,
      "status_counts": {
        "observed": 8,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 16
      }
    },
    "context_recall@1": {
      "status": "observed",
      "value": 0.6666666666666666,
      "mean": 0.6666666666666666,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.6666666666666666
      ],
      "numerator": 16.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "context_recall@3": {
      "status": "observed",
      "value": 0.6666666666666666,
      "mean": 0.6666666666666666,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.6666666666666666
      ],
      "numerator": 16.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "context_recall@5": {
      "status": "observed",
      "value": 0.6666666666666666,
      "mean": 0.6666666666666666,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.6666666666666666
      ],
      "numerator": 16.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "context_selection_loss@1": {
      "status": "observed",
      "value": 0.0,
      "mean": 0.0,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.0
      ],
      "numerator": 0.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "context_selection_loss@3": {
      "status": "observed",
      "value": 0.0,
      "mean": 0.0,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.0
      ],
      "numerator": 0.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "context_selection_loss@5": {
      "status": "observed",
      "value": 0.0,
      "mean": 0.0,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.0
      ],
      "numerator": 0.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "ranked_mrr": {
      "status": "observed",
      "value": 0.6666666666666666,
      "mean": 0.6666666666666666,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.6666666666666666
      ],
      "numerator": 16.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "ranked_recall@1": {
      "status": "observed",
      "value": 0.6666666666666666,
      "mean": 0.6666666666666666,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.6666666666666666
      ],
      "numerator": 16.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "ranked_recall@3": {
      "status": "observed",
      "value": 0.6666666666666666,
      "mean": 0.6666666666666666,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.6666666666666666
      ],
      "numerator": 16.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "ranked_recall@5": {
      "status": "observed",
      "value": 0.6666666666666666,
      "mean": 0.6666666666666666,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.6666666666666666
      ],
      "numerator": 16.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "raw_mrr": {
      "status": "observed",
      "value": 0.6666666666666666,
      "mean": 0.6666666666666666,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.6666666666666666
      ],
      "numerator": 16.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "raw_recall@1": {
      "status": "observed",
      "value": 0.6666666666666666,
      "mean": 0.6666666666666666,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.6666666666666666
      ],
      "numerator": 16.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "raw_recall@3": {
      "status": "observed",
      "value": 0.6666666666666666,
      "mean": 0.6666666666666666,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.6666666666666666
      ],
      "numerator": 16.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "raw_recall@5": {
      "status": "observed",
      "value": 0.6666666666666666,
      "mean": 0.6666666666666666,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.6666666666666666
      ],
      "numerator": 16.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "retrieval_stage_delta@1": {
      "status": "observed",
      "value": 0.0,
      "mean": 0.0,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.0
      ],
      "numerator": 0.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "retrieval_stage_delta@3": {
      "status": "observed",
      "value": 0.0,
      "mean": 0.0,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.0
      ],
      "numerator": 0.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "retrieval_stage_delta@5": {
      "status": "observed",
      "value": 0.0,
      "mean": 0.0,
      "standard_deviation": 0.0,
      "repetition_values": [
        0.0
      ],
      "numerator": 0.0,
      "denominator": 24,
      "errors": 0,
      "coverage": 1.0,
      "status_counts": {
        "observed": 24,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 0
      }
    },
    "unsupported_answer_rate": {
      "status": "observed",
      "value": 1.0,
      "mean": 1.0,
      "standard_deviation": 0.0,
      "repetition_values": [
        1.0
      ],
      "numerator": 8.0,
      "denominator": 8,
      "errors": 0,
      "coverage": 0.3333333333333333,
      "status_counts": {
        "observed": 8,
        "unavailable": 0,
        "not_applicable": 0,
        "error": 0,
        "needs_review": 16
      }
    }
  },
  "execution": {
    "expected": 24,
    "total": 24,
    "not_run": 0,
    "completed": 24,
    "timeout": 0,
    "system_error": 0,
    "cancelled": 0,
    "execution_failure_rate": 0.0
  }
}
```

## Cases

### gsm-id-01 · repetition 1

- Status: `completed`
- Question: Who owns policy POL-AR-12?
- Gold answer: `Office of Transit`
- Generated answer: `Policy POL-AR-12 is owned by the Office of Transit.

### References  
- [1] source-00003-f9b49d55f06b.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "retrieval_missing",
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [
    "a required evidence group is absent from raw retrieval"
  ],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-id-01",
  "evidence": [
    {
      "evidence_id": "id-01",
      "document_id": "explicit-id",
      "locator": {
        "type": "object",
        "object_type": "policy",
        "object_id": "POL-AR-12"
      },
      "canonical_value": "Office of Transit",
      "quote_anchor": null
    }
  ],
  "required_groups": [
    [
      "id-01"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.5007078725431833,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 2,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.283527608768283,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.2791748194962842,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.25262263704122506,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 5,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.2429002550959068,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.2398855493656702,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.5007078725431833,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 2,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.283527608768283,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.2791748194962842,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.25262263704122506,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 5,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.2429002550959068,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.2398855493656702,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.5007078725431833,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 2,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.283527608768283,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.2791748194962842,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.25262263704122506,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 5,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.2429002550959068,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  }
]
```

### gsm-plain-03 · repetition 1

- Status: `completed`
- Question: Who accepts volunteer registrations at Cedar Lane Library?
- Gold answer: `Nia Perez`
- Generated answer: `Volunteer coordinator Nia Perez accepts volunteer registrations at Cedar Lane Library.

### References  
- [1] source-00000-2fee8e922508.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-plain-03",
  "evidence": [
    {
      "evidence_id": "plain-03",
      "document_id": "plain-text",
      "locator": {
        "type": "text_span",
        "start": 111,
        "end": 187
      },
      "canonical_value": "Nia Perez",
      "quote_anchor": "Volunteer coordinator Nia Perez accepts registrations on Tuesday afternoons."
    }
  ],
  "required_groups": [
    [
      "plain-03"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.6612653326048182,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.40986158264676553,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.3960361105130366,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3260330057919498,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.30879007324490704,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 6,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.2790448934296519,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.6612653326048182,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.40986158264676553,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.3960361105130366,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3260330057919498,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.30879007324490704,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 6,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.2790448934296519,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.6612653326048182,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.40986158264676553,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.3960361105130366,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3260330057919498,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.30879007324490704,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  }
]
```

### gsm-table-04 · repetition 1

- Status: `completed`
- Question: What is the west row restock day in inventory-q2?
- Gold answer: `Monday`
- Generated answer: `The west row restock day in inventory-q2 is **Monday**.

This information is directly stated in the document chunk with reference_id "1", which specifies that for the row "west", the column "restock_day" has the value "Monday".

### References  
- [1] source-00002-f5bd71500cf7.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "retrieval_missing",
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [
    "a required evidence group is absent from raw retrieval"
  ],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-table-04",
  "evidence": [
    {
      "evidence_id": "table-04",
      "document_id": "table-cells",
      "locator": {
        "type": "table_cell",
        "table_id": "inventory-q2",
        "row": "west",
        "column": "restock_day"
      },
      "canonical_value": "Monday",
      "quote_anchor": null
    }
  ],
  "required_groups": [
    [
      "table-04"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.7271843107697585,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.42266353576132604,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.41483147534238635,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.33287068995652536,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3267588665834872,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.31770515823357703,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.7271843107697585,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.42266353576132604,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.41483147534238635,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.33287068995652536,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3267588665834872,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.31770515823357703,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.7271843107697585,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.42266353576132604,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.41483147534238635,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.33287068995652536,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3267588665834872,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  }
]
```

### gsm-table-02 · repetition 1

- Status: `completed`
- Question: How many units are recorded for the south row of inventory-q2?
- Gold answer: `31`
- Generated answer: `The south row of inventory-q2 has **31 units** recorded.

This information is directly stated in the content of the document chunk with reference_id "1", which specifies the value under the "units" column for the "south" row in the table "inventory-q2".

### References  
- [1] source-00002-f5bd71500cf7.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "retrieval_missing",
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [
    "a required evidence group is absent from raw retrieval"
  ],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-table-02",
  "evidence": [
    {
      "evidence_id": "table-02",
      "document_id": "table-cells",
      "locator": {
        "type": "table_cell",
        "table_id": "inventory-q2",
        "row": "south",
        "column": "units"
      },
      "canonical_value": "31",
      "quote_anchor": null
    }
  ],
  "required_groups": [
    [
      "table-02"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.6997728621196917,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4683706649253596,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 3,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4469446622571059,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.436221708942909,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3605477221098113,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.33683776432508605,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.6997728621196917,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4683706649253596,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 3,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4469446622571059,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.436221708942909,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3605477221098113,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.33683776432508605,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.6997728621196917,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4683706649253596,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 3,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4469446622571059,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.436221708942909,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3605477221098113,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  }
]
```

### gsm-multi-02 · repetition 1

- Status: `completed`
- Question: What are the field cart's sample-jar limit and backup-battery duration?
- Gold answer: `60 sample jars; 8 hours`
- Generated answer: `The field cart carries at most **60 sample jars** and its backup battery lasts for **8 hours**.

### References  
- [1] source-00004-07597626e952.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "generation_failure",
    "unsupported_answer"
  ],
  "certainty": "deterministic",
  "reasons": [
    "final context covered Gold Evidence but answer scorer failed",
    "completed answer is not deterministically grounded"
  ],
  "review_required": false
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-multi-02",
  "evidence": [
    {
      "evidence_id": "multi-02-capacity",
      "document_id": "multi-evidence",
      "locator": {
        "type": "text_span",
        "start": 90,
        "end": 136
      },
      "canonical_value": "60 sample jars",
      "quote_anchor": "The field cart carries at most 60 sample jars."
    },
    {
      "evidence_id": "multi-02-battery",
      "document_id": "multi-evidence",
      "locator": {
        "type": "text_span",
        "start": 137,
        "end": 177
      },
      "canonical_value": "8 hours",
      "quote_anchor": "The cart's backup battery lasts 8 hours."
    }
  ],
  "required_groups": [
    [
      "multi-02-capacity"
    ],
    [
      "multi-02-battery"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.5920065439853439,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.44609468714368644,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.428288688600062,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.41455292614829653,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.40521968126760033,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3046700297382698,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.5920065439853439,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.44609468714368644,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.428288688600062,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.41455292614829653,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.40521968126760033,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3046700297382698,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.5920065439853439,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.44609468714368644,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.428288688600062,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 4,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.41455292614829653,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.40521968126760033,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_groundedness",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  }
]
```

### gsm-plain-01 · repetition 1

- Status: `completed`
- Question: At what time does Cedar Lane Library open its reading room on weekdays?
- Gold answer: `08:30`
- Generated answer: `Cedar Lane Library opens its reading room at 08:30 on weekdays.

### References  
- [1] source-00000-2fee8e922508.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-plain-01",
  "evidence": [
    {
      "evidence_id": "plain-01",
      "document_id": "plain-text",
      "locator": {
        "type": "text_span",
        "start": 0,
        "end": 63
      },
      "canonical_value": "08:30",
      "quote_anchor": "Cedar Lane Library opens its reading room at 08:30 on weekdays."
    }
  ],
  "required_groups": [
    [
      "plain-01"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.744884008761829,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.49889581108920855,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.41886244652902016,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4127000392324258,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3627154359406311,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.33825724023346615,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.744884008761829,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.49889581108920855,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.41886244652902016,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4127000392324258,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3627154359406311,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.33825724023346615,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.744884008761829,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.49889581108920855,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.41886244652902016,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4127000392324258,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3627154359406311,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  }
]
```

### gsm-numeric-01 · repetition 1

- Status: `completed`
- Question: How much fluid does the cooling loop hold?
- Gold answer: `18.5`
- Generated answer: `The cooling loop holds 18.5 liters of fluid.

### References  
- [1] source-00001-3a802782eb43.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-numeric-01",
  "evidence": [
    {
      "evidence_id": "numeric-01",
      "document_id": "numeric-units",
      "locator": {
        "type": "text_span",
        "start": 0,
        "end": 44
      },
      "canonical_value": "18.5 liters",
      "quote_anchor": "The cooling loop holds 18.5 liters of fluid."
    }
  ],
  "required_groups": [
    [
      "numeric-01"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.7352466571222654,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.48202960268956746,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4039247616890189,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 4,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4039056935827188,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.35214108508499475,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3502597906321684,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.7352466571222654,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.48202960268956746,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4039247616890189,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 4,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4039056935827188,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.35214108508499475,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3502597906321684,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.7352466571222654,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.48202960268956746,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4039247616890189,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 4,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4039056935827188,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.35214108508499475,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  }
]
```

### gsm-numeric-03 · repetition 1

- Status: `completed`
- Question: At what frequency does the beacon emit?
- Gold answer: `915`
- Generated answer: `The beacon emits at **915 MHz**.

### References  
- [1] source-00001-3a802782eb43.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-numeric-03",
  "evidence": [
    {
      "evidence_id": "numeric-03",
      "document_id": "numeric-units",
      "locator": {
        "type": "text_span",
        "start": 105,
        "end": 133
      },
      "canonical_value": "915 MHz",
      "quote_anchor": "The beacon emits at 915 MHz."
    }
  ],
  "required_groups": [
    [
      "numeric-03"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.5712956053042725,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.38946541738070795,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 3,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.3594917611719822,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.35086940432276165,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.32265690051188795,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.2920584368323681,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.5712956053042725,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.38946541738070795,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 3,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.3594917611719822,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.35086940432276165,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.32265690051188795,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.2920584368323681,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.5712956053042725,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.38946541738070795,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 3,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.3594917611719822,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.35086940432276165,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.32265690051188795,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  }
]
```

### gsm-numeric-02 · repetition 1

- Status: `completed`
- Question: What torque is required for workshop calibration?
- Gold answer: `2.75`
- Generated answer: `Workshop calibration requires **2.75 newton-meters** of torque.

### References  
- [1] source-00001-3a802782eb43.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-numeric-02",
  "evidence": [
    {
      "evidence_id": "numeric-02",
      "document_id": "numeric-units",
      "locator": {
        "type": "text_span",
        "start": 45,
        "end": 104
      },
      "canonical_value": "2.75 newton-meters",
      "quote_anchor": "Workshop calibration requires 2.75 newton-meters of torque."
    }
  ],
  "required_groups": [
    [
      "numeric-02"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.6280980087592021,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.38368840522901393,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.3597670336882384,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.33530694502292135,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.31271642260199634,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.29450115878809474,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.6280980087592021,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.38368840522901393,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.3597670336882384,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.33530694502292135,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.31271642260199634,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.29450115878809474,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.6280980087592021,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.38368840522901393,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.3597670336882384,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.33530694502292135,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.31271642260199634,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  }
]
```

### gsm-abstain-01 · repetition 1

- Status: `completed`
- Question: Which parking permit is assigned in the visitor guide?
- Gold answer: `None`
- Generated answer: `The visitor guide does not assign parking permits. This information is explicitly stated in the content of the document chunk with reference_id "1": "The visitor guide lists room maps and opening hours. It does not assign parking permits."

### References  
- [1] source-00005-6694935e4e95.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "generation_failure",
    "unsupported_answer"
  ],
  "certainty": "deterministic",
  "reasons": [
    "final context covered Gold Evidence but answer scorer failed",
    "completed answer is not deterministically grounded"
  ],
  "review_required": false
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-abstain-01",
  "evidence": [
    {
      "evidence_id": "abstain-01",
      "document_id": "abstain-negative",
      "locator": {
        "type": "text_span",
        "start": 0,
        "end": 88
      },
      "canonical_value": "does not assign parking permits",
      "quote_anchor": "The visitor guide lists room maps and opening hours. It does not assign parking permits."
    }
  ],
  "required_groups": [
    [
      "abstain-01"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.6015863945825228,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.45530823915967905,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 3,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3482367292721248,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.3431121376019003,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3104858888937389,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.265547505168561,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.6015863945825228,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.45530823915967905,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 3,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3482367292721248,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.3431121376019003,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3104858888937389,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.265547505168561,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.6015863945825228,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.45530823915967905,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 3,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3482367292721248,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.3431121376019003,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3104858888937389,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_groundedness",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  }
]
```

### gsm-abstain-02 · repetition 1

- Status: `completed`
- Question: What staff phone number appears in the maintenance note?
- Gold answer: `None`
- Generated answer: `The maintenance note does not contain any staff phone numbers.  

### References  
- [2] source-00004-07597626e952.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "generation_failure",
    "unsupported_answer"
  ],
  "certainty": "deterministic",
  "reasons": [
    "final context covered Gold Evidence but answer scorer failed",
    "completed answer is not deterministically grounded"
  ],
  "review_required": false
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-abstain-02",
  "evidence": [
    {
      "evidence_id": "abstain-02",
      "document_id": "abstain-negative",
      "locator": {
        "type": "text_span",
        "start": 89,
        "end": 172
      },
      "canonical_value": "contains no staff phone numbers",
      "quote_anchor": "The maintenance note records filter dates only; it contains no staff phone numbers."
    }
  ],
  "required_groups": [
    [
      "abstain-02"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.5921154033915876,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4481323698418256,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4425187547240871,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 4,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.43721451431538394,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.42761703244031657,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.37604180936126674,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.5921154033915876,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4481323698418256,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4425187547240871,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 4,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.43721451431538394,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.42761703244031657,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.37604180936126674,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.5921154033915876,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4481323698418256,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4425187547240871,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 4,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.43721451431538394,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.42761703244031657,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_groundedness",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  }
]
```

### gsm-multi-04 · repetition 1

- Status: `completed`
- Question: What is the garden pavilion capacity and when does it close?
- Gold answer: `24 seats; rainfall`
- Generated answer: `The garden pavilion has a capacity of 24 seats and closes during rainfall.

### References  
- [1] source-00004-07597626e952.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "generation_failure",
    "unsupported_answer"
  ],
  "certainty": "deterministic",
  "reasons": [
    "final context covered Gold Evidence but answer scorer failed",
    "completed answer is not deterministically grounded"
  ],
  "review_required": false
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-multi-04",
  "evidence": [
    {
      "evidence_id": "multi-04-capacity",
      "document_id": "multi-evidence",
      "locator": {
        "type": "text_span",
        "start": 265,
        "end": 298
      },
      "canonical_value": "24 seats",
      "quote_anchor": "The garden pavilion has 24 seats."
    },
    {
      "evidence_id": "multi-04-rain",
      "document_id": "multi-evidence",
      "locator": {
        "type": "text_span",
        "start": 299,
        "end": 335
      },
      "canonical_value": "rainfall",
      "quote_anchor": "The pavilion closes during rainfall."
    }
  ],
  "required_groups": [
    [
      "multi-04-capacity"
    ],
    [
      "multi-04-rain"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.5624832379280419,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.39248817345710174,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3858495739109262,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3794675599403461,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.34499382530730865,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3355320298409021,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.5624832379280419,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.39248817345710174,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3858495739109262,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3794675599403461,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.34499382530730865,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3355320298409021,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.5624832379280419,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.39248817345710174,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3858495739109262,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3794675599403461,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.34499382530730865,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_groundedness",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  }
]
```

### gsm-id-02 · repetition 1

- Status: `completed`
- Question: Who owns policy POL-CM-08?
- Gold answer: `Civic Archive`
- Generated answer: `Policy POL-CM-08 is owned by the Civic Archive.

### References  
- [2] source-00005-6694935e4e95.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "retrieval_missing",
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [
    "a required evidence group is absent from raw retrieval"
  ],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-id-02",
  "evidence": [
    {
      "evidence_id": "id-02",
      "document_id": "explicit-id",
      "locator": {
        "type": "object",
        "object_type": "policy",
        "object_id": "POL-CM-08"
      },
      "canonical_value": "Civic Archive",
      "quote_anchor": null
    }
  ],
  "required_groups": [
    [
      "id-02"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4778030957401069,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 2,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.2831706567414712,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.26160286208758093,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.25793247263627567,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.25177338522080916,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 6,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.24535794518585585,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4778030957401069,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 2,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.2831706567414712,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.26160286208758093,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.25793247263627567,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.25177338522080916,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 6,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.24535794518585585,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4778030957401069,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 2,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.2831706567414712,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 3,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.26160286208758093,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.25793247263627567,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.25177338522080916,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  }
]
```

### gsm-table-03 · repetition 1

- Status: `completed`
- Question: What is the east row restock day in inventory-q2?
- Gold answer: `Thursday`
- Generated answer: `The east row restock day in inventory-q2 is **Thursday**.

This information is directly stated in the document chunk with reference_id "1", which contains a table entry for the "east" row under the "restock_day" column with the value "Thursday".

### References  
- [1] source-00002-f5bd71500cf7.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "retrieval_missing",
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [
    "a required evidence group is absent from raw retrieval"
  ],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-table-03",
  "evidence": [
    {
      "evidence_id": "table-03",
      "document_id": "table-cells",
      "locator": {
        "type": "table_cell",
        "table_id": "inventory-q2",
        "row": "east",
        "column": "restock_day"
      },
      "canonical_value": "Thursday",
      "quote_anchor": null
    }
  ],
  "required_groups": [
    [
      "table-03"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.7269837369999035,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4411517458187159,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.40196919038852197,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3290331607272775,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3243171001702189,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.3098163592595554,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.7269837369999035,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4411517458187159,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.40196919038852197,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3290331607272775,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3243171001702189,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.3098163592595554,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.7269837369999035,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4411517458187159,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.40196919038852197,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3290331607272775,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3243171001702189,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  }
]
```

### gsm-multi-03 · repetition 1

- Status: `completed`
- Question: Which intake form does River Lab use and how long does it remain valid?
- Gold answer: `slate forms; 14 days`
- Generated answer: `River Lab uses slate forms for intake requests, and each slate form expires after 14 days.

### References  
- [1] source-00004-07597626e952.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "generation_failure",
    "unsupported_answer"
  ],
  "certainty": "deterministic",
  "reasons": [
    "final context covered Gold Evidence but answer scorer failed",
    "completed answer is not deterministically grounded"
  ],
  "review_required": false
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-multi-03",
  "evidence": [
    {
      "evidence_id": "multi-03-form",
      "document_id": "multi-evidence",
      "locator": {
        "type": "text_span",
        "start": 178,
        "end": 225
      },
      "canonical_value": "slate forms",
      "quote_anchor": "River Lab uses slate forms for intake requests."
    },
    {
      "evidence_id": "multi-03-expiry",
      "document_id": "multi-evidence",
      "locator": {
        "type": "text_span",
        "start": 226,
        "end": 264
      },
      "canonical_value": "14 days",
      "quote_anchor": "Each slate form expires after 14 days."
    }
  ],
  "required_groups": [
    [
      "multi-03-form"
    ],
    [
      "multi-03-expiry"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.5645183500017087,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.3716330374590507,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 3,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.33808814593469655,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.337408478558572,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.31964785998144457,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.29845570043000347,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.5645183500017087,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.3716330374590507,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 3,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.33808814593469655,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.337408478558572,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.31964785998144457,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.29845570043000347,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.5645183500017087,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.3716330374590507,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 3,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.33808814593469655,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.337408478558572,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 5,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.31964785998144457,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_groundedness",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  }
]
```

### gsm-id-04 · repetition 1

- Status: `completed`
- Question: Who owns record REC-HB-03?
- Gold answer: `Harbor Board`
- Generated answer: `The record REC-HB-03 is owned by the Harbor Board.

### References  
- [4] source-00000-2fee8e922508.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "retrieval_missing",
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [
    "a required evidence group is absent from raw retrieval"
  ],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-id-04",
  "evidence": [
    {
      "evidence_id": "id-04",
      "document_id": "explicit-id",
      "locator": {
        "type": "object",
        "object_type": "record",
        "object_id": "REC-HB-03"
      },
      "canonical_value": "Harbor Board",
      "quote_anchor": null
    }
  ],
  "required_groups": [
    [
      "id-04"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.44112451176344164,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 2,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.27337199162457526,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 3,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.26803305223927126,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.25350026463453323,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.23550154688110997,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 6,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.22679212218004963,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.44112451176344164,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 2,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.27337199162457526,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 3,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.26803305223927126,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.25350026463453323,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.23550154688110997,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 6,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.22679212218004963,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.44112451176344164,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 2,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.27337199162457526,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 3,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.26803305223927126,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.25350026463453323,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.23550154688110997,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  }
]
```

### gsm-table-01 · repetition 1

- Status: `completed`
- Question: How many units are recorded for the north row of inventory-q2?
- Gold answer: `47`
- Generated answer: `The north row of inventory-q2 is recorded with **47 units**.

This information is directly stated in the content of the document chunk with reference_id "1", which specifies the value for the "north" row under the "units" column in the table "inventory-q2".

### References  
- [1] source-00002-f5bd71500cf7.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "retrieval_missing",
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [
    "a required evidence group is absent from raw retrieval"
  ],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-table-01",
  "evidence": [
    {
      "evidence_id": "table-01",
      "document_id": "table-cells",
      "locator": {
        "type": "table_cell",
        "table_id": "inventory-q2",
        "row": "north",
        "column": "units"
      },
      "canonical_value": "47",
      "quote_anchor": null
    }
  ],
  "required_groups": [
    [
      "table-01"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.7096088833325933,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 2,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.4533128491506816,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.45156571990803684,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.42078102201355516,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.36246394633474793,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.36186414610854234,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.7096088833325933,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 2,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.4533128491506816,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.45156571990803684,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.42078102201355516,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.36246394633474793,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.36186414610854234,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 1,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.7096088833325933,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 2,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.4533128491506816,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.45156571990803684,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.42078102201355516,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.36246394633474793,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  }
]
```

### gsm-plain-04 · repetition 1

- Status: `completed`
- Question: What is the label of the archive locker?
- Gold answer: `Birch-17`
- Generated answer: `The label of the archive locker is **Birch-17**.

### References  
- [1] source-00000-2fee8e922508.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-plain-04",
  "evidence": [
    {
      "evidence_id": "plain-04",
      "document_id": "plain-text",
      "locator": {
        "type": "text_span",
        "start": 188,
        "end": 227
      },
      "canonical_value": "Birch-17",
      "quote_anchor": "The archive locker is labeled Birch-17."
    }
  ],
  "required_groups": [
    [
      "plain-04"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.535093597110798,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4975626650927282,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 3,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.4379206558041802,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.4206623045123449,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 5,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4167549799485737,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 6,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.40953693088624854,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.535093597110798,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4975626650927282,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 3,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.4379206558041802,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.4206623045123449,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 5,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4167549799485737,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 6,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.40953693088624854,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.535093597110798,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4975626650927282,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 3,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.4379206558041802,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.4206623045123449,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 5,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4167549799485737,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  }
]
```

### gsm-abstain-03 · repetition 1

- Status: `completed`
- Question: Which allergy certifications are stated in the cafe notice?
- Gold answer: `None`
- Generated answer: `The cafe notice does not state any allergy certifications.  

### References  
- [1] source-00005-6694935e4e95.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "generation_failure",
    "unsupported_answer"
  ],
  "certainty": "deterministic",
  "reasons": [
    "final context covered Gold Evidence but answer scorer failed",
    "completed answer is not deterministically grounded"
  ],
  "review_required": false
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-abstain-03",
  "evidence": [
    {
      "evidence_id": "abstain-03",
      "document_id": "abstain-negative",
      "locator": {
        "type": "text_span",
        "start": 173,
        "end": 258
      },
      "canonical_value": "does not state any allergy certifications",
      "quote_anchor": "The cafe notice describes menu changes and does not state any allergy certifications."
    }
  ],
  "required_groups": [
    [
      "abstain-03"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.6287472819072969,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.41210109811387263,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.38753379455616876,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3609988747893527,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.3326369334927747,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 6,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3024701123165194,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.6287472819072969,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.41210109811387263,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.38753379455616876,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3609988747893527,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.3326369334927747,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 6,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3024701123165194,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.6287472819072969,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 2,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.41210109811387263,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.38753379455616876,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 4,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3609988747893527,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 5,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.3326369334927747,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_groundedness",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  }
]
```

### gsm-id-03 · repetition 1

- Status: `completed`
- Question: Who owns record REC-GL-44?
- Gold answer: `Greenhouse Lab`
- Generated answer: `Record REC-GL-44 is owned by the Greenhouse Lab.

### References  
- [3] source-00000-2fee8e922508.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "retrieval_missing",
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [
    "a required evidence group is absent from raw retrieval"
  ],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-id-03",
  "evidence": [
    {
      "evidence_id": "id-03",
      "document_id": "explicit-id",
      "locator": {
        "type": "object",
        "object_type": "record",
        "object_id": "REC-GL-44"
      },
      "canonical_value": "Greenhouse Lab",
      "quote_anchor": null
    }
  ],
  "required_groups": [
    [
      "id-03"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.43793206762241405,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 2,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3017314200115092,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 3,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.2741035189579596,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.26233711534303317,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 5,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.25691648551987306,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.2346092384300346,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.43793206762241405,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 2,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3017314200115092,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 3,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.2741035189579596,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.26233711534303317,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 5,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.25691648551987306,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.2346092384300346,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 1,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.43793206762241405,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 2,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3017314200115092,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 3,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.2741035189579596,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 4,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.26233711534303317,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 5,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.25691648551987306,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  }
]
```

### gsm-plain-02 · repetition 1

- Status: `completed`
- Question: Which level contains the quiet-study floor at Cedar Lane Library?
- Gold answer: `level 3`
- Generated answer: `The quiet-study floor at Cedar Lane Library is on level 3.

### References  
- [1] source-00000-2fee8e922508.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-plain-02",
  "evidence": [
    {
      "evidence_id": "plain-02",
      "document_id": "plain-text",
      "locator": {
        "type": "text_span",
        "start": 64,
        "end": 110
      },
      "canonical_value": "level 3",
      "quote_anchor": "The library's quiet-study floor is on level 3."
    }
  ],
  "required_groups": [
    [
      "plain-02"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.6992061962873037,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4005819948186238,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 3,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.38094181747862405,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.36117340463656505,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.32195192969827674,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.28121879118133913,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.6992061962873037,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4005819948186238,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 3,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.38094181747862405,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.36117340463656505,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.32195192969827674,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 6,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.28121879118133913,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 1,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.6992061962873037,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4005819948186238,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 3,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.38094181747862405,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.36117340463656505,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.32195192969827674,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "text contains a gold value but is not exact-normalized"
  }
]
```

### gsm-multi-01 · repetition 1

- Status: `completed`
- Question: What are the opening and closing times of the Coastline Exchange evening desk?
- Gold answer: `17:00 to 21:00`
- Generated answer: `The Coastline Exchange evening desk opens at 17:00 and closes at 21:00.

### References  
- [1] source-00004-07597626e952.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "generation_failure",
    "unsupported_answer"
  ],
  "certainty": "deterministic",
  "reasons": [
    "final context covered Gold Evidence but answer scorer failed",
    "completed answer is not deterministically grounded"
  ],
  "review_required": false
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-multi-01",
  "evidence": [
    {
      "evidence_id": "multi-01-open",
      "document_id": "multi-evidence",
      "locator": {
        "type": "text_span",
        "start": 0,
        "end": 55
      },
      "canonical_value": "17:00",
      "quote_anchor": "The Coastline Exchange opens its evening desk at 17:00."
    },
    {
      "evidence_id": "multi-01-close",
      "document_id": "multi-evidence",
      "locator": {
        "type": "text_span",
        "start": 56,
        "end": 89
      },
      "canonical_value": "21:00",
      "quote_anchor": "The evening desk closes at 21:00."
    }
  ],
  "required_groups": [
    [
      "multi-01-open"
    ],
    [
      "multi-01-close"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.7041371690427146,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 2,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.4604794415874658,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.40176207054801405,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3981547053072914,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3965422642095951,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.32863135878208993,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.7041371690427146,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 2,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.4604794415874658,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.40176207054801405,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3981547053072914,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3965422642095951,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 6,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.32863135878208993,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 1,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.7041371690427146,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 2,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.4604794415874658,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 3,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.40176207054801405,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.3981547053072914,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.3965422642095951,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 2.0,
    "denominator": 2.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_groundedness",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  }
]
```

### gsm-numeric-04 · repetition 1

- Status: `completed`
- Question: What is the weight of the packing crate?
- Gold answer: `12`
- Generated answer: `The packing crate weighs **12 kilograms**.

### References  
- [1] source-00001-3a802782eb43.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "needs_review"
  ],
  "certainty": "unknown",
  "reasons": [],
  "review_required": true
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-numeric-04",
  "evidence": [
    {
      "evidence_id": "numeric-04",
      "document_id": "numeric-units",
      "locator": {
        "type": "text_span",
        "start": 134,
        "end": 172
      },
      "canonical_value": "12 kilograms",
      "quote_anchor": "The packing crate weighs 12 kilograms."
    }
  ],
  "required_groups": [
    [
      "numeric-04"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.6313326842387257,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.45014998770401393,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 3,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4351406048275712,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4175756936245862,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.4139736590361571,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.34963168198713923,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.6313326842387257,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.45014998770401393,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 3,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4351406048275712,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4175756936245862,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.4139736590361571,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.34963168198713923,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 1,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.6313326842387257,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.45014998770401393,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 3,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.4351406048275712,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 4,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.4175756936245862,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 5,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.4139736590361571,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "answer_groundedness",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "needs_review",
    "value": null,
    "numerator": null,
    "denominator": null,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": "numeric answer contains an additional contradictory or ambiguous value"
  }
]
```

### gsm-abstain-04 · repetition 1

- Status: `completed`
- Question: What is the delivery driver's name in the shipping memo?
- Gold answer: `None`
- Generated answer: `The shipping memo does not provide the delivery driver's name. It only lists crate labels and gives no information about the delivery driver.

### References  
- [1] source-00005-6694935e4e95.txt`
- Failure reason: `None`

#### Failure Assessment

```json
{
  "labels": [
    "generation_failure",
    "unsupported_answer"
  ],
  "certainty": "deterministic",
  "reasons": [
    "final context covered Gold Evidence but answer scorer failed",
    "completed answer is not deterministically grounded"
  ],
  "review_required": false
}
```

#### Gold Evidence

```json
{
  "gold_evidence_set_id": "evidence-abstain-04",
  "evidence": [
    {
      "evidence_id": "abstain-04",
      "document_id": "abstain-negative",
      "locator": {
        "type": "text_span",
        "start": 259,
        "end": 330
      },
      "canonical_value": "no delivery driver name",
      "quote_anchor": "The shipping memo lists crate labels but gives no delivery driver name."
    }
  ],
  "required_groups": [
    [
      "abstain-04"
    ]
  ]
}
```

#### Raw Retrieved Evidence

```json
[
  {
    "item_id": "raw:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.5648737020139126,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4063350156911053,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 3,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.39485949608402415,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.3786203039637447,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.37690698648354437,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": null
    }
  },
  {
    "item_id": "raw:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3252311278027014,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": null
    }
  }
]
```

#### Ranked Evidence

```json
[
  {
    "item_id": "ranked:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.5648737020139126,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4063350156911053,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 3,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.39485949608402415,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.3786203039637447,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.37690698648354437,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "ranked:doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "rank": 6,
    "content": "Cedar Lane Library opens its reading room at 08:30 on weekdays.\nThe library's quiet-study floor is on level 3.\nVolunteer coordinator Nia Perez accepts registrations on Tuesday afternoons.\nThe archive locker is labeled Birch-17.",
    "document_id": "plain-text",
    "locator": null,
    "score": 0.3252311278027014,
    "token_count": null,
    "native_id": "doc-e3faf9469891e67c3f4d0eae30535d02-chunk-000",
    "metadata": {
      "file_path": "source-00000-2fee8e922508.txt",
      "source_type": "vector"
    }
  }
]
```

#### Final Context

```json
[
  {
    "item_id": "context:doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "rank": 1,
    "content": "The visitor guide lists room maps and opening hours. It does not assign parking permits.\nThe maintenance note records filter dates only; it contains no staff phone numbers.\nThe cafe notice describes menu changes and does not state any allergy certifications.\nThe shipping memo lists crate labels but gives no delivery driver name.",
    "document_id": "abstain-negative",
    "locator": null,
    "score": 0.5648737020139126,
    "token_count": null,
    "native_id": "doc-694835a57fa1c2ae21a9c77f4b50fd98-chunk-000",
    "metadata": {
      "file_path": "source-00005-6694935e4e95.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "rank": 2,
    "content": "[\n  {\"object_type\": \"policy\", \"object_id\": \"POL-AR-12\", \"owner\": \"Office of Transit\", \"topic\": \"bike storage\"},\n  {\"object_type\": \"policy\", \"object_id\": \"POL-CM-08\", \"owner\": \"Civic Archive\", \"topic\": \"map copying\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-GL-44\", \"owner\": \"Greenhouse Lab\", \"topic\": \"seed intake\"},\n  {\"object_type\": \"record\", \"object_id\": \"REC-HB-03\", \"owner\": \"Harbor Board\", \"topic\": \"dock lights\"}\n]",
    "document_id": "explicit-id",
    "locator": null,
    "score": 0.4063350156911053,
    "token_count": null,
    "native_id": "doc-fcdc1254b7c2e88c2409575e885412bc-chunk-000",
    "metadata": {
      "file_path": "source-00003-f9b49d55f06b.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "rank": 3,
    "content": "The cooling loop holds 18.5 liters of fluid.\nWorkshop calibration requires 2.75 newton-meters of torque.\nThe beacon emits at 915 MHz.\nThe packing crate weighs 12 kilograms.",
    "document_id": "numeric-units",
    "locator": null,
    "score": 0.39485949608402415,
    "token_count": null,
    "native_id": "doc-9395bfc4465662e2d5fd0b89032831b2-chunk-000",
    "metadata": {
      "file_path": "source-00001-3a802782eb43.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "rank": 4,
    "content": "The Coastline Exchange opens its evening desk at 17:00.\nThe evening desk closes at 21:00.\nThe field cart carries at most 60 sample jars.\nThe cart's backup battery lasts 8 hours.\nRiver Lab uses slate forms for intake requests.\nEach slate form expires after 14 days.\nThe garden pavilion has 24 seats.\nThe pavilion closes during rainfall.",
    "document_id": "multi-evidence",
    "locator": null,
    "score": 0.3786203039637447,
    "token_count": null,
    "native_id": "doc-d9613b6e1e69000a766e6fdd358fa3c1-chunk-000",
    "metadata": {
      "file_path": "source-00004-07597626e952.txt",
      "source_type": "vector"
    }
  },
  {
    "item_id": "context:doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "rank": 5,
    "content": "[\n  {\"table_id\": \"inventory-q2\", \"row\": \"north\", \"column\": \"units\", \"value\": \"47\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"south\", \"column\": \"units\", \"value\": \"31\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"east\", \"column\": \"restock_day\", \"value\": \"Thursday\"},\n  {\"table_id\": \"inventory-q2\", \"row\": \"west\", \"column\": \"restock_day\", \"value\": \"Monday\"}\n]",
    "document_id": "table-cells",
    "locator": null,
    "score": 0.37690698648354437,
    "token_count": null,
    "native_id": "doc-9c3ad8494d524b31511009377a71657f-chunk-000",
    "metadata": {
      "file_path": "source-00002-f5bd71500cf7.txt",
      "source_type": "vector"
    }
  }
]
```

#### Metric Breakdown

```json
[
  {
    "metric_id": "raw_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "raw_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "ranked_mrr",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@1",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@3",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_recall@5",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@1",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@3",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "retrieval_stage_delta@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "context_selection_loss@5",
    "status": "observed",
    "value": 0.0,
    "numerator": null,
    "denominator": null,
    "scorer_id": "provenance-evidence-groups",
    "scorer_version": "1.0",
    "scorer_digest": "sha256:3cb3e34df57cd4f7550837bbeeb960205e7822ba4c1c00d3e432c38984fc3238",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_accuracy",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": null,
    "reason": null
  },
  {
    "metric_id": "answer_groundedness",
    "status": "observed",
    "value": 0.0,
    "numerator": 0.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  },
  {
    "metric_id": "unsupported_answer_rate",
    "status": "observed",
    "value": 1.0,
    "numerator": 1.0,
    "denominator": 1.0,
    "scorer_id": "typed-answer",
    "scorer_version": "1.1",
    "scorer_digest": "sha256:b1b804b0b34fb1981805e3fbc52f2316bbbb4f0e9bef5b088bc7576943f12a0e",
    "evaluator_mode": "deterministic_gold_evidence",
    "reason": null
  }
]
```
