import { useEffect, useState, type FormEvent } from "react";
import {
  fetchLlmModels,
  fetchPiiEntityOptions,
  fetchTenantSettings,
  updateTenantSettings,
} from "../api/client";
import { useTenant } from "../context/TenantContext";
import { EntityChipPicker } from "./EntityChipPicker";
import { toEntityOptions } from "../lib/entityLabels";

const PROVIDERS = ["ollama", "groq", "gemini", "openai"];

export function SettingsPanel() {
  const { tenantSlug, isAdmin } = useTenant();
  const [llmProvider, setLlmProvider] = useState("ollama");
  const [llmModel, setLlmModel] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [entities, setEntities] = useState<string[]>([]);
  const [availableEntities, setAvailableEntities] = useState<string[]>([]);
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      setMessage(null);
      try {
        const [settings, entityPayload] = await Promise.all([
          fetchTenantSettings(tenantSlug),
          fetchPiiEntityOptions(),
        ]);
        if (cancelled) {
          return;
        }
        const provider = String(settings.llm_provider ?? "ollama");
        const baseUrl = String(settings.llm_base_url ?? "");
        setLlmProvider(provider);
        setLlmModel(String(settings.llm_model ?? ""));
        setLlmBaseUrl(baseUrl);
        setEntities(Array.isArray(settings.pii_entities) ? settings.pii_entities.map(String) : []);
        setAvailableEntities(
          Array.isArray(entityPayload.entities) ? entityPayload.entities.map(String) : [],
        );
        const models = await fetchLlmModels(provider, baseUrl);
        if (!cancelled) {
          setModelOptions(Array.isArray(models.models) ? models.models.map(String) : []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load settings.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [tenantSlug]);

  useEffect(() => {
    let cancelled = false;
    async function loadModels() {
      try {
        const models = await fetchLlmModels(llmProvider, llmBaseUrl);
        if (!cancelled) {
          setModelOptions(Array.isArray(models.models) ? models.models.map(String) : []);
        }
      } catch {
        if (!cancelled) {
          setModelOptions([]);
        }
      }
    }
    void loadModels();
    return () => {
      cancelled = true;
    };
  }, [llmProvider, llmBaseUrl]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await updateTenantSettings(tenantSlug, {
        llm_provider: llmProvider,
        llm_model: llmModel,
        llm_base_url: llmBaseUrl,
        llm_api_key: llmApiKey.trim() || undefined,
        pii_entities: entities,
      });
      setLlmApiKey("");
      setMessage("Settings saved for this tenant.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h1>Settings</h1>
        <p>
          Configure LLM and PII options for tenant <strong>{tenantSlug}</strong>.
          {isAdmin ? " Admin can edit any tenant from the selector." : ""}
        </p>
      </header>

      {loading ? <p className="result-muted">Loading settings...</p> : null}

      <form className="process-form settings-form" onSubmit={onSubmit}>
        <fieldset className="settings-fieldset">
          <legend>LLM</legend>
          <label className="field">
            <span>Provider</span>
            <select value={llmProvider} onChange={(event) => setLlmProvider(event.target.value)}>
              {PROVIDERS.map((provider) => (
                <option key={provider} value={provider}>
                  {provider}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Model</span>
            <select value={llmModel} onChange={(event) => setLlmModel(event.target.value)}>
              <option value="">Select a model</option>
              {modelOptions.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Base URL</span>
            <input
              type="text"
              value={llmBaseUrl}
              onChange={(event) => setLlmBaseUrl(event.target.value)}
              placeholder="http://ollama:11434/v1"
            />
          </label>

          <label className="field">
            <span>API key (optional, leave blank to keep current)</span>
            <input
              type="password"
              value={llmApiKey}
              onChange={(event) => setLlmApiKey(event.target.value)}
              autoComplete="off"
            />
          </label>
        </fieldset>

        <fieldset className="settings-fieldset">
          <legend>PII entities</legend>
          <EntityChipPicker
            options={toEntityOptions(availableEntities)}
            selectedIds={entities}
            onChange={setEntities}
          />
        </fieldset>

        <button type="submit" className="primary-button" disabled={saving || loading}>
          {saving ? "Saving..." : "Save settings"}
        </button>
      </form>

      {message ? <p className="success-banner">{message}</p> : null}
      {error ? <p className="error-banner">{error}</p> : null}
    </section>
  );
}
