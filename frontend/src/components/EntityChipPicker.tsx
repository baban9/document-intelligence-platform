import type { EntityOption } from "../lib/entityLabels";

type EntityChipPickerProps = {
  options: EntityOption[];
  selectedIds: string[];
  disabled?: boolean;
  onChange: (selectedIds: string[]) => void;
};

export function EntityChipPicker({
  options,
  selectedIds,
  disabled = false,
  onChange,
}: EntityChipPickerProps) {
  const selected = new Set(selectedIds);

  function toggle(id: string) {
    if (disabled) {
      return;
    }
    const next = new Set(selected);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onChange(Array.from(next));
  }

  return (
    <div className="chip-grid" role="group" aria-label="PII types to detect">
      {options.map((option) => {
        const isSelected = selected.has(option.id);
        return (
          <button
            key={option.id}
            type="button"
            className={`chip ${isSelected ? "chip-selected" : ""}`}
            aria-pressed={isSelected}
            disabled={disabled}
            onClick={() => toggle(option.id)}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function summarizeSelection(
  selectedIds: string[],
  options: EntityOption[],
  vertical?: string,
): string {
  if (vertical?.trim()) {
    return `Preset "${vertical}" controls entity selection.`;
  }
  if (!selectedIds.length) {
    return "No PII types selected.";
  }
  const labels = options
    .filter((option) => selectedIds.includes(option.id))
    .map((option) => option.label);
  const preview = labels.slice(0, 12).join(", ");
  const suffix = labels.length > 12 ? `, and ${labels.length - 12} more` : "";
  return `${labels.length} types selected: ${preview}${suffix}`;
}
