"""Command-line launcher for an isolated adapter worker."""

from __future__ import annotations

import argparse
import importlib
import os
from collections.abc import Callable

import uvicorn

from rag_eval.worker.app import WorkerDefinition, create_worker_app


def load_factory(spec: str) -> Callable[[], WorkerDefinition]:
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("adapter factory must use module:function syntax")
    module = importlib.import_module(module_name)
    factory = getattr(module, attribute)
    if not callable(factory):
        raise TypeError("adapter factory is not callable")
    return factory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-factory", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", required=True, type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    allow_container_bind = os.environ.get("RAG_EVAL_WORKER_ALLOW_CONTAINER_BIND") == "1"
    if args.host != "127.0.0.1" and not (allow_container_bind and args.host == "0.0.0.0"):
        raise SystemExit("adapter workers may bind only to 127.0.0.1")
    token = os.environ.get("RAG_EVAL_WORKER_TOKEN", "")
    if not token:
        raise SystemExit("RAG_EVAL_WORKER_TOKEN is required")
    definition = load_factory(args.adapter_factory)()
    app = create_worker_app(definition, token=token, run_id=args.run_id)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
