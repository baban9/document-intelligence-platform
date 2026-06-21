# Monitoring integration

This folder holds configs you can drop into your existing observability stack.

| Path | Use when |
|------|----------|
| [../docs/MONITORING.md](../docs/MONITORING.md) | Full integration guide (start here) |
| [prometheus/prometheus.yml](prometheus/prometheus.yml) | Bundled Prometheus for `make up` / `make docker-up-monitoring` |
| [prometheus/scrape-config.example.yml](prometheus/scrape-config.example.yml) | Add DocIntel to your own Prometheus |
| [prometheus/alert-rules.yml](prometheus/alert-rules.yml) | Example alert rules |
| [kubernetes/servicemonitor.yaml](kubernetes/servicemonitor.yaml) | Prometheus Operator on Kubernetes |
| [kubernetes/prometheusrule.yaml](kubernetes/prometheusrule.yaml) | Alert rules for Prometheus Operator |
| [integrations/datadog-openmetrics.yaml.example](integrations/datadog-openmetrics.yaml.example) | Datadog Agent OpenMetrics check |
| [grafana/dashboards/docintel-app-performance.json](grafana/dashboards/docintel-app-performance.json) | Import into Grafana |

Quick scrape target:

```text
GET http://<api-host>:5000/metrics?format=prometheus
```

The metrics endpoint is unauthenticated by default so scrapers can reach it without API keys.
