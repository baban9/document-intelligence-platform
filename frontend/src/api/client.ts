const API_BASE = import.meta.env.VITE_API_BASE ?? "";

type JsonRecord = Record<string, unknown>;

async function parseJson(response: Response): Promise<JsonRecord> {
  const payload = (await response.json()) as JsonRecord;
  if (!response.ok) {
    const message =
      typeof payload.error === "string" ? payload.error : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

export async function fetchHealth(): Promise<string> {
  const response = await fetch(`${API_BASE}/health`);
  const payload = await parseJson(response);
  return typeof payload.status === "string" ? payload.status : "unknown";
}

export async function fetchPiiEntities(): Promise<string[]> {
  const response = await fetch(`${API_BASE}/v1/pdf/entities`);
  const payload = await parseJson(response);
  const supported = payload.supported_entities;
  if (Array.isArray(supported)) {
    return supported.map(String).sort();
  }
  return [];
}

export type ProcessOptions = {
  sentences: number;
  includeSummary: boolean;
  includePii: boolean;
  includeText: boolean;
  vertical?: string;
  entities?: string[];
};

export async function processDocument(
  file: File,
  options: ProcessOptions,
): Promise<JsonRecord> {
  const form = new FormData();
  form.append("file", file);
  form.append("sentences", String(options.sentences));
  form.append("include_summarize", String(options.includeSummary));
  form.append("include_pii", String(options.includePii));
  form.append("include_text", String(options.includeText));
  if (options.vertical?.trim()) {
    form.append("vertical", options.vertical.trim());
  } else if (options.entities?.length) {
    form.append("entities", options.entities.join(","));
  }

  const response = await fetch(`${API_BASE}/v1/documents/process`, {
    method: "POST",
    body: form,
  });
  return parseJson(response);
}
