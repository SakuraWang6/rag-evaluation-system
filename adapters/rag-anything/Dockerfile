# Build from the RAG workspace root:
# docker build -f evaluation-system/adapters/rag-anything/Dockerfile -t rag-eval-adapter-rag-anything:0.1.0 .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/rag-eval
COPY evaluation-system/platform /opt/rag-eval/platform
COPY evaluation-system/adapters/rag-anything /opt/rag-eval/adapter
# RAG-Anything validates the configured parser during initialization even for
# source-only TXT/Markdown ingestion.  Keep MinerU explicit so the standard
# image fails neither at handshake nor at the first fresh Worker run.
RUN pip install --no-cache-dir /opt/rag-eval/platform /opt/rag-eval/adapter "mineru>=3.4,<3.5" \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin ragworker
# MinerU imports OpenCV during its documented `mineru --version` health check.
# Python slim omits these native libraries by default.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgl1 libglib2.0-0 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

USER 10001:10001
ENTRYPOINT ["python", "-m", "rag_eval.worker.main"]
