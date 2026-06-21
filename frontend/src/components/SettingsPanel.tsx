import { useEffect, useState, type FormEvent } from "react";
import {
  fetchLlmModels,
  fetchPiiEntityOptions,
  fetchPiiPresets,
  fetchTenantSettings,
  revealTenantApiKey,
  updateTenantSettings,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useTenant } from "../context/TenantContext";
import { EntityChipPicker } from "./EntityChipPicker";
import { ModelPickerModal } from "./ModelPickerModal";
import { toEntityOptions } from "../lib/entityLabels";

const PROVIDERS = ["ollama", "groq", "gemini", "openai"];
const PRESET_ORDER = ["general", "healthcare", "financial", "legal"];
const LIVE_MODEL_PROVIDERS = new Set(["ollama", "groq", "gemini", "openai"]);

function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function SettingsPanel() {
  const { tenantSlug, isAdmin } = useTenant();
  const { user: authUser } = useAuth();
  const [llmProvider, setLlmProvider] = useState("ollama");
  const [llmModel, setLlmModel] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [apiKeySet, setApiKeySet] = useState(false);
  const [apiKeyOwnerMatch, setApiKeyOwnerMatch] = useState(false);
  const [apiKeyLocked, setApiKeyLocked] = useState(false);
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [revealingKey, setRevealingKey] = useState(false);
  const [entities, setEntities] = useState<string[]>([]);
  const [availableEntities, setAvailableEntities] = useState<string[]>([]);
  const [presetMap, setPresetMap] = useState<Record<string, string[]>>({});
  const [activePreset, setActivePreset] = useState("");
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [modelSource, setModelSource] = useState<string | null>(null);
  const [modelWarning, setModelWarning] = useState<string | null>(null);
  const [modelModalOpen, setModelModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [refreshingModels, setRefreshingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [piiWarning, setPiiWarning] = useState<string | null>(null);

  async function refreshModels(
    provider = llmProvider,
    baseUrl = llmBaseUrl,
    options?: { openModal?: boolean },
  ) {
    if (options?.openModal) {
      setModelModalOpen(true);
    }
    setRefreshingModels(true);
    setError(null);
    try {
      const models = await fetchLlmModels(provider, baseUrl, {
        apiKey: llmApiKey,
        tenantSlug,
      });
      setModelOptions(Array.isArray(models.models) ? models.models.map(String) : []);
      setModelSource(models.source ?? null);
      setModelWarning(models.warning ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not refresh model list.");
      setModelOptions([]);
      setModelSource(null);
      setModelWarning(null);
    } finally {
      setRefreshingModels(false);
    }
  }

  function handleProviderChange(nextProvider: string) {
    setLlmProvider(nextProvider);
    if (LIVE_MODEL_PROVIDERS.has(nextProvider)) {
      void refreshModels(nextProvider, llmBaseUrl, { openModal: true });
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
        setApiKeyOwnerMatch(Boolean(settings.llm_api_key_owner_match));
        setApiKeyLocked(Boolean(settings.llm_api_key_locked));
        setRevealedKey(null);
        setShowKey(false);
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

  async function onRevealApiKey() {
    setRevealingKey(true);
    setError(null);
    try {
      const key = await revealTenantApiKey(tenantSlug);
      setRevealedKey(key);
      setShowKey(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reveal API key.");
    } finally {
      setRevealingKey(false);
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
      setApiKeyOwnerMatch(Boolean(updated.llm_api_key_owner_match));
      setApiKeyLocked(Boolean(updated.llm_api_key_locked));
      setLlmApiKey("");
      setRevealedKey(null);
      setShowKey(false);
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
            <select
              value={llmProvider}
              onChange={(event) => handleProviderChange(event.target.value)}
            >
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
              <input
                type="text"
                value={llmModel}
                onChange={(event) => setLlmModel(event.target.value)}
                placeholder="Select or type a model id"
                list="settings-model-options"
              />
              <datalist id="settings-model-options">
                {modelOptions.map((model) => (
                  <option key={model} value={model} />
                ))}
              </datalist>
            </label>
            <button
              type="button"
              className="secondary-button"
              disabled={refreshingModels || loading}
              onClick={() => void refreshModels(llmProvider, llmBaseUrl, { openModal: true })}
            >
              {refreshingModels ? "Loading..." : "Browse models"}
            </button>
          </div>
          {modelSource ? <p className="result-muted">Model list source: {modelSource}</p> : null}
          {modelWarning ? <p className="error-banner">{modelWarning}</p> : null}

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
            {apiKeySet && apiKeyLocked ? (
              <p className="result-muted">
                An API key is configured by another user on this device. You cannot view or replace it.
              </p>
            ) : null}
            {apiKeySet && apiKeyOwnerMatch ? (
              <p className="settings-masked-key">
                {authUser?.authenticated
                  ? `Your API key is stored for ${authUser.email || authUser.subject}. Only you can view or replace it.`
                  : "Your API key is stored with user-only encryption. Sign in with OIDC to use the same owner on every device."}
              </p>
            ) : null}
            {apiKeySet && !apiKeyOwnerMatch && !apiKeyLocked ? (
              <p className="result-muted">An API key is configured for this tenant.</p>
            ) : null}
            {!apiKeySet ? <p className="result-muted">No API key stored for this tenant.</p> : null}

            {apiKeySet && apiKeyOwnerMatch ? (
              <div className="settings-key-reveal-row">
                {showKey && revealedKey ? (
                  <input type="text" readOnly value={revealedKey} className="settings-revealed-key" />
                ) : (
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={revealingKey || loading}
                    onClick={() => void onRevealApiKey()}
                  >
                    {revealingKey ? "Loading..." : "Show my API key"}
                  </button>
                )}
                {showKey && revealedKey ? (
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => setShowKey(false)}
                  >
                    Hide
                  </button>
                ) : null}
              </div>
            ) : null}

            {!apiKeyLocked ? (
              <input
                type="password"
                value={llmApiKey}
                onChange={(event) => setLlmApiKey(event.target.value)}
                placeholder={
                  apiKeySet && apiKeyOwnerMatch
                    ? "Enter a new key to replace your stored value"
                    : "Enter an API key for this provider"
                }
                autoComplete="off"
              />
            ) : null}
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

      <ModelPickerModal
        open={modelModalOpen}
        provider={llmProvider}
        models={modelOptions}
        source={modelSource}
        warning={modelWarning}
        loading={refreshingModels}
        selectedModel={llmModel}
        onSelect={setLlmModel}
        onClose={() => setModelModalOpen(false)}
      />

      {message ? <p className="success-banner">{message}</p> : null}
      {piiWarning ? <p className="error-banner">{piiWarning}</p> : null}
      {error ? <p className="error-banner">{error}</p> : null}
    </section>
  );
}
