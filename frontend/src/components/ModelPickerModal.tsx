import { useEffect, useMemo, useState } from "react";

type ModelPickerModalProps = {
  open: boolean;
  provider: string;
  models: string[];
  source: string | null;
  warning: string | null;
  loading: boolean;
  selectedModel: string;
  onSelect: (model: string) => void;
  onClose: () => void;
};

export function ModelPickerModal({
  open,
  provider,
  models,
  source,
  warning,
  loading,
  selectedModel,
  onSelect,
  onClose,
}: ModelPickerModalProps) {
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (open) {
      setQuery("");
    }
  }, [open, provider]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return models;
    }
    return models.filter((model) => model.toLowerCase().includes(needle));
  }, [models, query]);

  if (!open) {
    return null;
  }

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="model-picker-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <h2 id="model-picker-title">Choose {provider} model</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            x
          </button>
        </header>

        {loading ? <p className="result-muted">Fetching models from {provider}...</p> : null}
        {!loading && source ? (
          <p className="result-muted">Source: {source}{warning ? ` (${warning})` : ""}</p>
        ) : null}

        <label className="field">
          <span>Search</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter models..."
            autoFocus
          />
        </label>

        <ul className="model-picker-list">
          {filtered.map((model) => (
            <li key={model}>
              <button
                type="button"
                className={`model-picker-item${selectedModel === model ? " model-picker-item-active" : ""}`}
                onClick={() => {
                  onSelect(model);
                  onClose();
                }}
              >
                {model}
              </button>
            </li>
          ))}
          {!loading && filtered.length === 0 ? (
            <li className="result-muted">No models match your search.</li>
          ) : null}
        </ul>

        <footer className="modal-footer">
          <button type="button" className="secondary-button" onClick={onClose}>
            Cancel
          </button>
        </footer>
      </div>
    </div>
  );
}
