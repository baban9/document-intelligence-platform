# Monitoring integration examples

This folder holds **copy-paste configs** for your own observability stack. DocIntel does not ship Prometheus, Grafana, or Loki in `docker-compose.yml`.

| Path | Use when |
|------|----------|
| [../docs/MONITORING.md](../docs/MONITORING.md) | Full integration guide (start here) |
| [prometheus/scrape-config.example.yml](prometheus/scrape-config.example.yml) | Add DocIntel to your Prometheus |
| [prometheus/prometheus.yml](prometheus/prometheus.yml) | Reference Prometheus file (adjust scrape targets) |
| [prometheus/alert-rules.yml](prometheus/alert-rules.yml) | Example alert rules |
| [kubernetes/servicemonitor.yaml](kubernetes/servicemonitor.yaml) | Prometheus Operator on Kubernetes |
| [kubernetes/prometheusrule.yaml](kubernetes/prometheusrule.yaml) | Alert rules for Prometheus Operator |
| [integrations/datadog-openmetrics.yaml.example](integrations/datadog-openmetrics.yaml.example) | Datadog Agent OpenMetrics check |
| [grafana/dashboards/docintel-app-performance.json](grafana/dashboards/docintel-app-performance.json) | Import into your Grafana |
| [grafana/dashboards/docintel-logs.json](grafana/dashboards/docintel-logs.json) | Import into your Grafana (Loki) |
| [loki/loki-config.yml](loki/loki-config.yml) | Example single-node Loki config |
| [promtail/promtail-config.yml](promtail/promtail-config.yml) | Example Promtail config for container logs |

Quick scrape target:

```text
GET http://<api-host>:5000/metrics?format=prometheus
```

The metrics endpoint is unauthenticated by default so scrapers can reach it without API keys. Restrict network access in production.
