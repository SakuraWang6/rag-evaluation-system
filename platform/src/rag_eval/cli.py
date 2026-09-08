"""Local CLI for the standalone RAG evaluation platform."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import uvicorn

from rag_eval.api import create_app
from rag_eval.artifact_contract import freeze_artifact
from rag_eval.comparison import validate_comparison
from rag_eval.contracts.research import (
    AnalysisContract,
    ComparisonSpec,
    LatencyProtocol,
    ModelLock,
)
from rag_eval.contracts.run import ComparisonTier, ExperimentSpec
from rag_eval.contracts.schema import export_json_schemas
from rag_eval.datasets.blind import validate_blind_layout
from rag_eval.replay import replay_mismatches
from rag_eval.service import PlatformService
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.layout import PlatformPaths
from rag_eval.systems import SystemRegistration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")

    dataset = subparsers.add_parser("register-dataset")
    dataset.add_argument("path", type=Path)

    system = subparsers.add_parser("register-system")
    system.add_argument("system_id")
    system.add_argument("adapter_id")
    system.add_argument("adapter_factory")
    system.add_argument("--python", default=sys.executable)
    system.add_argument("--environment-json", default="{}")
    system.add_argument("--timeout", type=float, default=180.0)

    fake = subparsers.add_parser("register-fake")
    fake.add_argument("--python", default=sys.executable)
    fake.add_argument("--pythonpath")

    experiment = subparsers.add_parser("create-experiment")
    experiment.add_argument("spec", type=Path)

    run = subparsers.add_parser("run")
    run.add_argument("experiment_id")

    compare = subparsers.add_parser("compare")
    compare.add_argument("tier", choices=[item.value for item in ComparisonTier])
    compare.add_argument("run_ids", nargs="+")
    compare.add_argument("--spec", type=Path)

    lock = subparsers.add_parser("freeze-model-lock")
    lock.add_argument("source", type=Path)
    lock.add_argument("destination", type=Path)

    latency = subparsers.add_parser("freeze-latency-protocol")
    latency.add_argument("source", type=Path)
    latency.add_argument("destination", type=Path)

    analysis = subparsers.add_parser("freeze-analysis-contract")
    analysis.add_argument("source", type=Path)
    analysis.add_argument("destination", type=Path)

    comparison_spec = subparsers.add_parser("freeze-comparison-spec")
    comparison_spec.add_argument("source", type=Path)
    comparison_spec.add_argument("destination", type=Path)

    blind = subparsers.add_parser("validate-blind-layout")
    blind.add_argument("public_root", type=Path)
    blind.add_argument("sealed_root", type=Path)

    verify = subparsers.add_parser("verify-run")
    verify.add_argument("run_id")

    replay = subparsers.add_parser("replay")
    replay.add_argument("run_id")
    replay.add_argument("--new-run-id")
    replay.add_argument("--allow-drift", action="store_true")

    schemas = subparsers.add_parser("export-schemas")
    schemas.add_argument("output", type=Path)

    serve = subparsers.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = PlatformPaths(args.home.expanduser() if args.home else PlatformPaths.from_environment().home)
    service = PlatformService(paths)
    if args.command == "init":
        print(paths.home)
    elif args.command == "register-dataset":
        print(service.datasets.register(args.path).bundle_id)
    elif args.command == "register-system":
        environment = json.loads(args.environment_json)
        registration = SystemRegistration(
            system_id=args.system_id,
            adapter_id=args.adapter_id,
            adapter_factory=args.adapter_factory,
            # Keep a virtual-environment interpreter symlink intact. Resolving it
            # selects the base interpreter and silently loses worker-only packages.
            python_executable=str(Path(args.python).expanduser().absolute()),
            environment=environment,
            request_timeout_seconds=args.timeout,
        )
        print(service.systems.register(registration))
    elif args.command == "register-fake":
        environment = {}
        if args.pythonpath:
            environment["PYTHONPATH"] = args.pythonpath
        registration = SystemRegistration(
            system_id="fake-rag",
            adapter_id="fake",
            adapter_factory="rag_eval.adapters.fake:create_worker_definition",
            python_executable=str(Path(args.python).resolve()),
            environment=environment,
        )
        print(service.systems.register(registration))
    elif args.command == "create-experiment":
        experiment = ExperimentSpec.model_validate_json(args.spec.read_text(encoding="utf-8"))
        service.admit_new_public_experiment(
            experiment, service.datasets.get(experiment.bundle_id)
        )
        print(service.experiments.create(experiment))
    elif args.command == "run":
        experiment = service.experiments.get(args.experiment_id)
        service.admit_new_public_experiment(
            experiment, service.datasets.get(experiment.bundle_id)
        )
        job = service.jobs.create(experiment)
        service.supervisor.run_once()
        print(service.jobs.get(job.job_id).model_dump_json(indent=2))
    elif args.command == "compare":
        spec = (
            ComparisonSpec.model_validate_json(args.spec.read_text(encoding="utf-8"))
            if args.spec
            else None
        )
        manifests = [service.runs.get(run_id) for run_id in args.run_ids]
        summaries = {
            manifest.run_id: json.loads(
                (service.paths.runs / manifest.run_id / "summary.json").read_text(
                    encoding="utf-8"
                )
            )
            for manifest in manifests
        }
        decision = validate_comparison(
            manifests,
            ComparisonTier(args.tier),
            summaries=summaries,
            spec=spec,
        )
        print(json.dumps(asdict(decision), default=str, indent=2))
        return 0 if decision.compatible else 2
    elif args.command == "verify-run":
        verification = service.runs.verify_artifacts(args.run_id)
        print(json.dumps(asdict(verification), indent=2))
        return 0 if verification.valid else 2
    elif args.command == "replay":
        verification = service.runs.verify_artifacts(args.run_id)
        if not verification.valid:
            print(json.dumps(asdict(verification), indent=2), file=sys.stderr)
            return 2
        original = service.runs.get(args.run_id)
        experiment = service.runs.experiment(args.run_id)
        resolved = service.system_resolver.resolve(experiment.system_id)
        replayed = service.executor.execute(
            experiment,
            resolved.command,
            run_id=args.new_run_id,
            replay_of_run_id=original.run_id,
            execution_metadata=resolved.execution_metadata,
        )
        mismatches = replay_mismatches(original, replayed)
        report = {
            "replay_of_run_id": original.run_id,
            "run_id": replayed.run_id,
            "allow_drift": args.allow_drift,
            "mismatches": mismatches,
        }
        mismatch_path = service.paths.runs / replayed.run_id / "replay-mismatch.json"
        atomic_write_json(mismatch_path, report)
        replayed = replayed.model_copy(
            update={
                "artifacts": {
                    **replayed.artifacts,
                    "replay_mismatch": "replay-mismatch.json",
                }
            }
        )
        service.runs.write_manifest(replayed)
        replayed = replayed.model_copy(
            update={"artifact_checksums": service.runs.artifact_hashes(replayed.run_id)}
        )
        service.runs.write_manifest(replayed)
        print(json.dumps({"manifest": replayed.model_dump(mode="json"), **report}, indent=2))
        if mismatches and not args.allow_drift:
            return 2
    elif args.command == "freeze-model-lock":
        lock = ModelLock.model_validate_json(args.source.read_text(encoding="utf-8"))
        digest = freeze_artifact(lock, args.destination)
        print(json.dumps({"path": str(args.destination), "digest": digest}, indent=2))
    elif args.command == "freeze-latency-protocol":
        protocol = LatencyProtocol.model_validate_json(
            args.source.read_text(encoding="utf-8")
        )
        digest = freeze_artifact(protocol, args.destination)
        print(json.dumps({"path": str(args.destination), "digest": digest}, indent=2))
    elif args.command == "freeze-analysis-contract":
        contract = AnalysisContract.model_validate_json(
            args.source.read_text(encoding="utf-8")
        )
        digest = freeze_artifact(contract, args.destination)
        print(json.dumps({"path": str(args.destination), "digest": digest}, indent=2))
    elif args.command == "freeze-comparison-spec":
        comparison_spec = ComparisonSpec.model_validate_json(
            args.source.read_text(encoding="utf-8")
        )
        digest = freeze_artifact(comparison_spec, args.destination)
        print(json.dumps({"path": str(args.destination), "digest": digest}, indent=2))
    elif args.command == "validate-blind-layout":
        report = validate_blind_layout(args.public_root, args.sealed_root)
        print(
            json.dumps(
                {
                    "public_root": str(report.public_root),
                    "sealed_root": str(report.sealed_root),
                    "sealed_bundle_digest": report.protocol.sealed_bundle_digest,
                },
                indent=2,
            )
        )
    elif args.command == "export-schemas":
        for path in export_json_schemas(args.output):
            print(path)
    elif args.command == "serve":
        if args.host != "127.0.0.1":
            raise SystemExit("the local-first server binds only to 127.0.0.1")
        uvicorn.run(create_app(service), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
