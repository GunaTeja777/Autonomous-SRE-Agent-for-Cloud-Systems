# Autonomous SRE Agent for Cloud Systems

Autonomous SRE Agent is a production-style service that monitors Kubernetes workloads,
detects anomalies, performs root cause analysis (RCA), and executes safe remediation
with verification and postmortem reporting.

## Features
- Continuous monitoring via Prometheus, Loki, Jaeger, and Kubernetes API.
- Threshold and ML-based anomaly detection.
- RCA via specialist agents with consensus.
- Runbook retrieval using a vector store (ChromaDB).
- Remediation planning (LLM or rule-based fallback).
- Risk assessment and gated execution.
- Post-remediation verification and incident reporting.

## Quickstart (Docker Compose)
1. Edit `.env` and set `ANTHROPIC_API_KEY`.
2. From this folder:

```bash
docker compose up --build
```

API is available at `http://localhost:8000`.

## Quickstart (Local)
```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API
- `GET /health`
- `POST /api/trigger` body: `{ "namespace": "default" }`
- `GET /api/incidents`
- `GET /api/incidents/{id}`
- `GET /api/incidents/{id}/report`
- `POST /api/incidents/{id}/approve`
- `GET /api/dashboard`

## Data
- `data/runbooks`: markdown runbooks loaded at startup.
- `data/embeddings`: ChromaDB persistence.
- `data/dashboards/summary.json`: exported dashboard summary.

## Safety Defaults
- `AUTO_REMEDIATE=false`
- `DRY_RUN=true`
- Risk assessment can gate remediation and require manual approval.
