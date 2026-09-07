# Build from the RAG workspace root:
# docker build -f evaluation-system/adapters/lightrag/Dockerfile -t rag-eval-adapter-lightrag:0.1.0 .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/rag-eval
COPY evaluation-system/platform /opt/rag-eval/platform
COPY evaluation-system/adapters/lightrag /opt/rag-eval/adapter
COPY rags/LightRAG /opt/rag-eval/lightrag
# Build the Worker against the checked-in LightRAG revision.  The public PyPI
# release can lag its official Docker/API surface; the enclosing image digest
# records the exact source and dependency result used for a run.
RUN pip install --no-cache-dir /opt/rag-eval/platform \
    && pip install --no-cache-dir "/opt/rag-eval/lightrag[api]" "ollama>=0.4,<1" /opt/rag-eval/adapter \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin ragworker

USER 10001:10001
ENTRYPOINT ["python", "-m", "rag_eval.worker.main"]
