const COUNTRY_PREFIX = /^[A-Z]{2}$/;

export function formatEntityLabel(entityId: string): string {
  const cleaned = entityId.trim();
  if (!cleaned) {
    return "";
  }

  const parts = cleaned.split("_").filter(Boolean);
  if (parts.length >= 2 && COUNTRY_PREFIX.test(parts[0])) {
    const country = parts[0];
    const rest = parts.slice(1).map((word) => word.toLowerCase()).join(" ");
    return `${country} ${rest}`;
  }

  const phrase = parts.map((word) => word.toLowerCase()).join(" ");
  return phrase ? phrase[0].toUpperCase() + phrase.slice(1) : "";
}

export type EntityOption = {
  id: string;
  label: string;
};

export function toEntityOptions(entityIds: string[]): EntityOption[] {
  return entityIds.map((id) => ({ id, label: formatEntityLabel(id) }));
}
