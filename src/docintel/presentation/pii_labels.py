"""Human-readable labels for Presidio PII entity types."""

from __future__ import annotations


def format_pii_entity_label(entity_id: str) -> str:
    """Convert CREDIT_CARD to Credit card, US_DRIVER_LICENSE to US driver license."""
    cleaned = entity_id.strip()
    if not cleaned:
        return ""

    parts = [part for part in cleaned.split("_") if part]
    if len(parts) >= 2 and len(parts[0]) == 2 and parts[0].isalpha() and parts[0].isupper():
        country = parts[0]
        rest = " ".join(word.lower() for word in parts[1:])
        return f"{country} {rest}"

    phrase = " ".join(word.lower() for word in parts)
    return phrase[0].upper() + phrase[1:] if phrase else ""


def pii_entity_choice_pairs(entity_ids: list[str]) -> list[tuple[str, str]]:
    """Gradio CheckboxGroup choices as (label, value) pairs."""
    return [(format_pii_entity_label(entity_id), entity_id) for entity_id in entity_ids]


def summarize_pii_entity_selection(
    *,
    selected_entity_ids: list[str] | None = None,
    vertical: str = "",
) -> str:
    """Short markdown summary of the active PII entity selection."""
    if vertical.strip():
        from docintel.capabilities.compliance.presets import entities_for_vertical

        try:
            entity_ids = list(entities_for_vertical(vertical))
        except ValueError:
            entity_ids = list(selected_entity_ids or [])
        labels = [format_pii_entity_label(entity_id) for entity_id in entity_ids]
        if not labels:
            return f"Preset **{vertical}** selected, but no entity types were resolved."
        preview = ", ".join(labels[:10])
        if len(labels) > 10:
            preview += f", and {len(labels) - 10} more"
        return f"**{len(labels)} types** from preset **{vertical}**: {preview}"

    entity_ids = list(selected_entity_ids or [])
    if not entity_ids:
        return "No PII types selected. Choose types below or pick a vertical preset."

    labels = [format_pii_entity_label(entity_id) for entity_id in entity_ids]
    preview = ", ".join(labels[:12])
    if len(labels) > 12:
        preview += f", and {len(labels) - 12} more"
    return f"**{len(labels)} types selected:** {preview}"
