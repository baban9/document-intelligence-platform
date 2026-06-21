import { useEffect, useState, type FormEvent } from "react";
import {
  fetchLlmModels,
  fetchPiiEntityOptions,
  fetchPiiPresets,
  fetchTenantSettings,
  updateTenantSettings,
} from "../api/client";
import { useTenant } from "../context/TenantContext";
import { EntityChipPicker } from "./EntityChipPicker";
import { toEntityOptions } from "../lib/entityLabels";

const PROVIDERS = ["ollama", "groq", "gemini", "openai"];
const PRESET_ORDER = ["general", "healthcare", "financial", "legal"];

function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function SettingsPanel() {
  const { tenantSlug, isAdmin } = useTenant();
  const [llmProvider, setLlmProvider] = useState("ollama");
  const [llmModel, setLlmModel] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [apiKeySet, setApiKeySet] = useState(false);
  const [entities, setEntities] = useState<string[]>([]);
  const [availableEntities, setAvailableEntities] = useState<string[]>([]);
  const [presetMap, setPresetMap] = useState<Record<string, string[]>>({});
  const [activePreset, setActivePreset] = useState("");
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [modelSource, setModelSource] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshingModels, setRefreshingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [piiWarning, setPiiWarning] = useState<string | null>(null);

  async function refreshModels(provider = llmProvider, baseUrl = llmBaseUrl) {
    setRefreshingModels(true);
    setError(null);
    try {
      const models = await fetchLlmModels(provider, baseUrl);
      setModelOptions(Array.isArray(models.models) ? models.models.map(String) : []);
      setModelSource(models.source ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not refresh model list.");
      setModelOptions([]);
      setModelSource(null);
    } finally {
      setRefreshingModels(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      setMessage(null);
      setPiiWarning(null);
      try {
        const [settings, entityPayload, presets] = await Promise.all([
          fetchTenantSettings(tenantSlug),
          fetchPiiEntityOptions(),
          fetchPiiPresets(),
        ]);
        if (cancelled) {
          return;
        }
        const provider = String(settings.llm_provider ?? "ollama");
        const baseUrl = String(settings.llm_base_url ?? "");
        setLlmProvider(provider);
        setLlmModel(String(settings.llm_model ?? ""));
        setLlmBaseUrl(baseUrl);
        setApiKeySet(Boolean(settings.llm_api_key_set));
        setEntities(Array.isArray(settings.pii_entities) ? settings.pii_entities.map(String) : []);
        setAvailableEntities(
          Array.isArray(entityPayload.entities) ? entityPayload.entities.map(String) : [],
        );
        setPresetMap(presets);
        setActivePreset("");
        await refreshModels(provider, baseUrl);
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

  function applyPreset(name: string) {
    setActivePreset(name);
    if (!name) {
      return;
    }
    const presetEntities = presetMap[name];
    if (presetEntities?.length) {
      setEntities(presetEntities);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPiiWarning(null);

    if (!entities.length) {
      const proceed = window.confirm(
        "No PII entities are selected. Save anyway? Scans will fall back to platform defaults.",
      );
      if (!proceed) {
        setPiiWarning("Save cancelled. Select at least one PII entity or confirm saving with none.");
        return;
      }
    }

    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await updateTenantSettings(tenantSlug, {
        llm_provider: llmProvider,
        llm_model: llmModel,
        llm_base_url: llmBaseUrl,
        llm_api_key: llmApiKey.trim() || undefined,
        pii_entities: entities,
      });
      setApiKeySet(Boolean(updated.llm_api_key_set));
      setLlmApiKey("");
      setMessage("Settings saved for this tenant.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save settings.");
    } finally {
      setSaving(false);
    }
  }

  const presetNames = PRESET_ORDER.filter((name) => presetMap[name]);

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

          <div className="field-row settings-model-row">
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
            <button
              type="button"
              className="secondary-button"
              disabled={refreshingModels || loading}
              onClick={() => void refreshModels()}
            >
              {refreshingModels ? "Refreshing..." : "Refresh models"}
            </button>
          </div>
          {modelSource ? <p className="result-muted">Model list source: {modelSource}</p> : null}

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
            <span>API key</span>
            {apiKeySet ? (
              <p className="settings-masked-key">Current key: configured (stored securely)</p>
            ) : (
              <p className="result-muted">No API key stored for this tenant.</p>
            )}
            <input
              type="password"
              value={llmApiKey}
              onChange={(event) => setLlmApiKey(event.target.value)}
              placeholder="Enter a new key to replace the stored value"
              autoComplete="off"
            />
          </label>
        </fieldset>

        <fieldset className="settings-fieldset">
          <legend>PII entities</legend>
          <label className="field">
            <span>Vertical preset</span>
            <select value={activePreset} onChange={(event) => applyPreset(event.target.value)}>
              <option value="">Manual selection</option>
              {presetNames.map((name) => (
                <option key={name} value={name}>
                  {titleCase(name)}
                </option>
              ))}
            </select>
          </label>
          <EntityChipPicker
            options={toEntityOptions(availableEntities)}
            selectedIds={entities}
            disabled={Boolean(activePreset)}
            onChange={(next) => {
              setActivePreset("");
              setEntities(next);
            }}
          />
        </fieldset>

        <button type="submit" className="primary-button" disabled={saving || loading}>
          {saving ? "Saving..." : "Save settings"}
        </button>
      </form>

      {message ? <p className="success-banner">{message}</p> : null}
      {piiWarning ? <p className="error-banner">{piiWarning}</p> : null}
      {error ? <p className="error-banner">{error}</p> : null}
    </section>
  );
}
