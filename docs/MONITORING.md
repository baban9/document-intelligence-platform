# Monitoring and observability

Document Intelligence exposes Prometheus metrics from the API process. You can use the bundled Prometheus and Grafana stack for local demos, or connect your existing monitoring in a few minutes.

## Metrics endpoint

| Item | Value |
|------|-------|
| URL | `GET /metrics?format=prometheus` |
| Auth | None (public path, same as `/health`) |
| Content type | Prometheus text exposition 0.0.4 |
| JSON fallback | `GET /metrics` (no query param) returns in-process JSON counters |

Verify from any machine that can reach the API:

```bash
curl -s "http://127.0.0.1:5000/metrics?format=prometheus" | head
```

Disable export if needed:

```bash
DOCINTEL_PROMETHEUS_ENABLED=false
```

## Metric catalog

All series use the `docintel_` prefix.

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| `docintel_http_requests_total` | Counter | `endpoint`, `status` | HTTP requests handled |
| `docintel_http_errors_total` | Counter | `endpoint`, `status` | Requests with status 4xx or 5xx |
| `docintel_http_request_duration_seconds` | Histogram | `endpoint` | Request wall time |
| `docintel_http_requests_in_flight` | Gauge | `endpoint` | Requests currently processing |
| `docintel_jobs_queued_total` | Counter | `job_type` | Background jobs enqueued |
| `docintel_jobs_finished_total` | Counter | `job_type`, `status` | Jobs completed or failed |
| `docintel_jobs_running` | Gauge | `job_type` | Jobs currently running |
| `docintel_job_duration_seconds` | Histogram | `job_type`, `status` | Job wall time |
| `docintel_rq_queue_depth` | Gauge | (none) | RQ jobs waiting in Redis |
| `docintel_redis_up` | Gauge | (none) | 1 if Redis ping succeeds, else 0 |
| `docintel_build_info` | Info | `version`, `service` | Build metadata |

Useful PromQL starting points:

```promql
# Request rate
sum(rate(docintel_http_requests_total[5m]))

# Error ratio (4xx and 5xx)
sum(rate(docintel_http_errors_total[5m]))
/ clamp_min(sum(rate(docintel_http_requests_total[5m])), 0.001)

# HTTP latency p95
histogram_quantile(0.95, sum(rate(docintel_http_request_duration_seconds_bucket[5m])) by (le))

# Job failure ratio
sum(rate(docintel_jobs_finished_total{status="failed"}[10m]))
/ clamp_min(sum(rate(docintel_jobs_finished_total[10m])), 0.001)
```

## Choose an integration path

### Option A: Bundled stack (fastest local setup)

Starts Redis, API, worker, Prometheus, and Grafana with a prebuilt dashboard.

```bash
make docker-up-monitoring
```

| Service | URL |
|---------|-----|
| Grafana | http://127.0.0.1:3000 (default admin / admin) |
| Prometheus | http://127.0.0.1:9090 |
| Metrics scrape | http://127.0.0.1:5000/metrics?format=prometheus |

Config files: `monitoring/prometheus/`, `monitoring/grafana/`.

### Option B: Your own Prometheus

1. Copy the scrape block from [monitoring/prometheus/scrape-config.example.yml](../monitoring/prometheus/scrape-config.example.yml).
2. Paste it into your Prometheus `scrape_configs`.
3. Replace `DOCINTEL_API_HOST` with your API host.
4. Reload or restart Prometheus.

Minimal scrape config:

```yaml
scrape_configs:
  - job_name: docintel-api
    scrape_interval: 15s
    metrics_path: /metrics
    params:
      format: [prometheus]
    static_configs:
      - targets: ["your-api-host:5000"]
        labels:
          service: docintel-api
```

Optional alert rules: mount [monitoring/prometheus/alert-rules.yml](../monitoring/prometheus/alert-rules.yml) and add to `rule_files` in your Prometheus config.

### Option C: Kubernetes (Prometheus Operator)

1. Expose the API with a Service named `docintel-api`, label `app: docintel-api`, port name `http` on 5000.
2. Apply the ServiceMonitor:

```bash
kubectl apply -f monitoring/kubernetes/servicemonitor.yaml
```

3. Apply alert rules:

```bash
kubectl apply -f monitoring/kubernetes/prometheusrule.yaml
```

If your Prometheus uses `serviceMonitorSelector` or `ruleSelector`, add matching labels to the manifests (for example `release: prometheus` for kube-prometheus-stack).

Example Service snippet:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: docintel-api
  labels:
    app: docintel-api
spec:
  selector:
    app: docintel-api
  ports:
    - name: http
      port: 5000
      targetPort: 5000
```

### Option D: Grafana only

You already have Prometheus or another compatible backend.

1. Add a Prometheus data source pointing at your Prometheus URL.
2. Import the dashboard JSON:
   - File: [monitoring/grafana/dashboards/docintel-app-performance.json](../monitoring/grafana/dashboards/docintel-app-performance.json)
   - Grafana UI: Dashboards -> New -> Import -> Upload JSON
3. Dashboard UID: `docintel-app-performance`

### Option E: Grafana Cloud or remote Prometheus

Grafana Cloud Agent, Alloy, or Grafana Agent Flow can scrape the same endpoint.

```yaml
scrape_configs:
  - job_name: docintel-api
    static_configs:
      - targets: ["your-api-host:5000"]
    metrics_path: /metrics
    params:
      format: [prometheus]
```

Forward scraped metrics to your Grafana Cloud Prometheus remote write endpoint using your vendor docs.

### Option F: Datadog OpenMetrics

Datadog can poll Prometheus endpoints with an OpenMetrics check.

```yaml
instances:
  - openmetrics_endpoint: http://your-api-host:5000/metrics?format=prometheus
    namespace: docintel
    metrics:
      - docintel_*
```

Place this in your Datadog Agent `conf.d/openmetrics.d/conf.yaml` and restart the agent. A ready-made file is at [monitoring/integrations/datadog-openmetrics.yaml.example](../monitoring/integrations/datadog-openmetrics.yaml.example).

### Option G: Amazon Managed Prometheus (AMP)

1. Run Prometheus Agent or Grafana Alloy in the cluster or on a host near the API.
2. Scrape `http://<api>:5000/metrics?format=prometheus` with the scrape config above.
3. Remote-write to your AMP workspace endpoint with IAM auth per AWS docs.

No code changes are required on the DocIntel side.

## Alert rules

Example rules ship in:

- Bare Prometheus: [monitoring/prometheus/alert-rules.yml](../monitoring/prometheus/alert-rules.yml)
- Kubernetes: [monitoring/kubernetes/prometheusrule.yaml](../monitoring/kubernetes/prometheusrule.yaml)

| Alert | Trigger |
|-------|---------|
| DocintelRedisDown | `docintel_redis_up == 0` for 2m |
| DocintelHighHTTPErrorRate | Error ratio above 10% for 5m |
| DocintelHighHTTPLatency | HTTP p95 above 30s for 5m |
| DocintelQueueBacklog | RQ depth above 50 for 10m |
| DocintelJobFailureRate | Failed job ratio above 20% for 10m |

Tune thresholds to match your traffic and SLOs.

## Security notes

- `/metrics` is on the public path list and does not require API keys. This matches common Prometheus practice.
- Restrict network access to the metrics port (VPC, security group, NetworkPolicy) if the API is on the public internet.
- Do not put secrets in metric labels. Current metrics expose route names and HTTP status codes only.
- Set `DOCINTEL_PROMETHEUS_ENABLED=false` if you must disable exposition entirely.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DOCINTEL_PROMETHEUS_ENABLED` | `true` | Set `false` to disable Prometheus series collection |
| `DOCINTEL_REDIS_URL` | `redis://localhost:6379/0` | Used for `docintel_redis_up` and queue depth |
| `DOCINTEL_JOBS_ENABLED` | `true` | When false, job metrics stay at zero |
| `PROMETHEUS_PORT` | `9090` | Bundled Prometheus host port (compose only) |
| `GRAFANA_PORT` | `3000` | Bundled Grafana host port (compose only) |

## File index

See [monitoring/README.md](../monitoring/README.md) for a short map of all config files in the repo.

## Related docs

- [PLATFORM.md](PLATFORM.md) - Ops layer overview
- [PRODUCTION.md](PRODUCTION.md) - Production checklist
