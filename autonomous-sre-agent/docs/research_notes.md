# Research Notes

## Objectives
- Reduce mean time to detect (MTTD) and mean time to recovery (MTTR).
- Provide consistent, evidence-backed RCA summaries.
- Enable safe automation with explicit risk gating.

## Assumptions
- Prometheus has access to container and pod metrics (kube-state-metrics, cAdvisor).
- Loki aggregates pod logs with namespace and pod labels.
- Jaeger traces include service names matching pod prefixes.

## Limitations
- No built-in Prometheus metrics are emitted by the API service.
- LLM-based reasoning depends on external API availability.
- Runbooks are static and require updates as services evolve.

## Evaluation Ideas
- Compare RCA accuracy against historical incidents.
- Track false positive rate of anomaly detection.
- Measure remediation success rate and rollback frequency.

## Future Improvements
- Add Prometheus instrumentation for API and workflow metrics.
- Dynamic thresholds based on historical baselines.
- More granular risk models using SLO impact.
- Expanded runbook library with service-specific actions.
