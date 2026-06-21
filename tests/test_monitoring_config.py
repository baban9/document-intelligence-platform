"""Tests for Prometheus and Grafana monitoring config."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MONITORING = ROOT / "monitoring"


def test_prometheus_scrape_config_targets_api():
    config_path = MONITORING / "prometheus" / "prometheus.yml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert "alert-rules.yml" in payload["rule_files"]
    jobs = payload["scrape_configs"]
    assert len(jobs) == 1
    job = jobs[0]
    assert job["job_name"] == "docintel-api"
    assert job["metrics_path"] == "/metrics"
    assert job["params"]["format"] == ["prometheus"]
    assert job["static_configs"][0]["targets"] == ["api:5000"]


def test_prometheus_scrape_example_has_required_fields():
    config_path = MONITORING / "prometheus" / "scrape-config.example.yml"
    jobs = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    job = jobs[0]
    assert job["job_name"] == "docintel-api"
    assert job["metrics_path"] == "/metrics"
    assert job["params"]["format"] == ["prometheus"]


def test_prometheus_alert_rules_load():
    rules_path = MONITORING / "prometheus" / "alert-rules.yml"
    payload = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    group = payload["groups"][0]
    names = {rule["alert"] for rule in group["rules"]}
    assert "DocintelRedisDown" in names
    assert "DocintelHighHTTPErrorRate" in names


def test_kubernetes_servicemonitor_scrapes_metrics():
    manifest_path = MONITORING / "kubernetes" / "servicemonitor.yaml"
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "ServiceMonitor"
    endpoint = payload["spec"]["endpoints"][0]
    assert endpoint["path"] == "/metrics"
    assert endpoint["params"]["format"] == ["prometheus"]


def test_kubernetes_prometheusrule_matches_bare_rules():
    k8s_path = MONITORING / "kubernetes" / "prometheusrule.yaml"
    bare_path = MONITORING / "prometheus" / "alert-rules.yml"
    k8s_rules = yaml.safe_load(k8s_path.read_text(encoding="utf-8"))
    bare_rules = yaml.safe_load(bare_path.read_text(encoding="utf-8"))
    k8s_names = {rule["alert"] for rule in k8s_rules["spec"]["groups"][0]["rules"]}
    bare_names = {rule["alert"] for rule in bare_rules["groups"][0]["rules"]}
    assert k8s_names == bare_names


def test_grafana_dashboard_is_valid_json():
    dashboard_path = MONITORING / "grafana" / "dashboards" / "docintel-app-performance.json"
    import json

    payload = json.loads(dashboard_path.read_text(encoding="utf-8"))
    assert payload["uid"] == "docintel-app-performance"
    assert payload["title"] == "Document Intelligence - App Performance"
    assert len(payload["panels"]) >= 4


def test_monitoring_readme_exists():
    readme = MONITORING / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "docs/MONITORING.md" in text
    assert "scrape-config.example.yml" in text
