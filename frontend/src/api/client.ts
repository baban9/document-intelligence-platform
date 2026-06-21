import { loadTenantSlug, TENANT_HEADER } from "../lib/tenantStorage";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

type JsonRecord = Record<string, unknown>;

export type { JsonRecord };

async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers ?? {});
  headers.set(TENANT_HEADER, loadTenantSlug());
  return fetch(input, { ...init, headers });
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function parseJson(response: Response): Promise<JsonRecord> {
  const payload = (await response.json()) as JsonRecord;
  if (response.status < 200 || response.status >= 300) {
    const message =
      typeof payload.error === "string" ? payload.error : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

function unwrapJobResult(payload: JsonRecord): JsonRecord {
  const nested = payload.result;
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    return { ...payload, ...(nested as JsonRecord) };
  }
  return payload;
}

export async function postFormAsync(
  path: string,
  form: FormData,
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  const separator = path.includes("?") ? "&" : "?";
  const response = await apiFetch(`${API_BASE}${path}${separator}async=true`, {
    method: "POST",
    body: form,
  });
  const payload = await parseJson(response);

  if (typeof payload.poll_url === "string") {
    onProgress?.({
      jobStatus: String(payload.job_status || "queued"),
      message: String(payload.message || "Job queued"),
      progress: Number(payload.progress ?? 0),
    });
    const completed = await pollJobUntilComplete(payload.poll_url, onProgress);
    return unwrapJobResult(completed);
  }

  return unwrapJobResult(payload);
}

export async function postJsonAsync(
  path: string,
  body: JsonRecord,
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  const response = await apiFetch(`${API_BASE}${path}?async=true`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await parseJson(response);

  if (typeof payload.poll_url === "string") {
    onProgress?.({
      jobStatus: String(payload.job_status || "queued"),
      message: String(payload.message || "Job queued"),
      progress: Number(payload.progress ?? 0),
    });
    const completed = await pollJobUntilComplete(payload.poll_url, onProgress);
    return unwrapJobResult(completed);
  }

  return unwrapJobResult(payload);
}

export async function downloadJobPdf(
  payload: JsonRecord,
  fallbackName: string,
): Promise<{ blobUrl: string; filename: string }> {
  const result = unwrapJobResult(payload);
  const downloadPath =
    typeof payload.download_url === "string"
      ? payload.download_url
      : typeof result.download_url === "string"
        ? (result.download_url as string)
        : null;

  if (!downloadPath) {
    throw new Error("Processed PDF is not ready yet.");
  }

  const response = await apiFetch(`${API_BASE}${downloadPath}`);
  if (!response.ok) {
    throw new Error("Processed PDF could not be downloaded.");
  }
  const blob = await response.blob();
  const filename = downloadPath.split("/").pop() || fallbackName;
  return { blobUrl: URL.createObjectURL(blob), filename };
}

export async function fetchHealth(): Promise<string> {
  const response = await apiFetch(`${API_BASE}/health`);
  const payload = await parseJson(response);
  return typeof payload.status === "string" ? payload.status : "unknown";
}

export async function fetchPiiEntities(): Promise<string[]> {
  const response = await apiFetch(`${API_BASE}/v1/pdf/entities`);
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

export type ProcessResult = {
  filename?: string;
  identification?: JsonRecord;
  extraction?: JsonRecord;
  classification?: JsonRecord;
  summary?: JsonRecord;
  pii?: JsonRecord;
};

export type ProgressUpdate = {
  jobStatus: string;
  message: string;
  progress: number;
};

export async function pollJobUntilComplete(
  pollUrl: string,
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  const deadline = Date.now() + 600_000;
  while (Date.now() < deadline) {
    const response = await apiFetch(`${API_BASE}${pollUrl}`);
    const payload = await parseJson(response);
    const jobStatus = String(payload.job_status || "unknown");
    const message = String(payload.progress_message || jobStatus);
    const progress = Number(payload.progress ?? 0);
    onProgress?.({ jobStatus, message, progress });

    if (jobStatus === "completed") {
      return payload;
    }
    if (jobStatus === "failed") {
      throw new Error(String(payload.error || "Job failed."));
    }
    await sleep(2000);
  }
  throw new Error("Job timed out while waiting for results.");
}

export function unwrapProcessResult(payload: JsonRecord): ProcessResult {
  const nested = payload.result;
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    return nested as ProcessResult;
  }
  if (payload.classification || payload.extraction || payload.summary || payload.pii) {
    return payload as ProcessResult;
  }
  throw new Error("The API returned a job response without process results.");
}

export async function processDocument(
  file: File,
  options: ProcessOptions,
  onProgress?: (update: ProgressUpdate) => void,
): Promise<ProcessResult> {
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

  const response = await apiFetch(`${API_BASE}/v1/documents/process?async=true`, {
    method: "POST",
    body: form,
  });
  const payload = await parseJson(response);

  if (typeof payload.poll_url === "string") {
    onProgress?.({
      jobStatus: String(payload.job_status || "queued"),
      message: String(payload.message || "Job queued"),
      progress: Number(payload.progress ?? 0),
    });
    const completed = await pollJobUntilComplete(payload.poll_url, onProgress);
    return unwrapProcessResult(completed);
  }

  return unwrapProcessResult(payload);
}

export async function analyzeIntegrity(
  input: { file?: File; text?: string; checks: string[] },
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  if (input.file) {
    const form = new FormData();
    form.append("file", input.file);
    if (input.checks.length) {
      form.append("checks", input.checks.join(","));
    }
    return postFormAsync("/v1/documents/analyze-integrity", form, onProgress);
  }
  if (!input.text?.trim()) {
    throw new Error("Upload a document or paste text to analyze.");
  }
  return postJsonAsync(
    "/v1/documents/analyze-integrity",
    {
      text: input.text.trim(),
      ...(input.checks.length ? { checks: input.checks } : {}),
    },
    onProgress,
  );
}

export async function identifyDocument(file: File): Promise<JsonRecord> {
  const form = new FormData();
  form.append("file", file);
  const response = await apiFetch(`${API_BASE}/v1/documents/identify`, {
    method: "POST",
    body: form,
  });
  return parseJson(response);
}

export async function extractDocumentText(
  file: File,
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  const form = new FormData();
  form.append("file", file);
  const result = await postFormAsync("/v1/documents/extract-text", form, onProgress);
  const text = typeof result.text === "string" ? result.text : "";
  if (text.length > 2000) {
    return {
      ...result,
      text_preview: `${text.slice(0, 2000)}\n...(truncated)`,
      text: undefined,
    };
  }
  return result;
}

export async function classifyDocument(
  file: File,
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  const form = new FormData();
  form.append("file", file);
  return postFormAsync("/v1/documents/classify", form, onProgress);
}

export async function summarizeDocument(
  file: File,
  sentences: number,
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  const form = new FormData();
  form.append("file", file);
  form.append("sentences", String(sentences));
  return postFormAsync("/v1/documents/summarize", form, onProgress);
}

export async function detectPiiDocument(
  file: File,
  entities: string[],
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  const form = new FormData();
  form.append("file", file);
  if (entities.length) {
    form.append("entities", entities.join(","));
  }
  return postFormAsync("/v1/documents/detect-pii", form, onProgress);
}

export async function compareDocuments(
  fileA: File,
  fileB: File,
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  const form = new FormData();
  form.append("file_a", fileA);
  form.append("file_b", fileB);
  return postFormAsync("/v1/documents/compare", form, onProgress);
}

export type AnnotatePdfOptions = {
  action: string;
  pattern?: string;
  requirements?: string;
};

export async function annotatePdf(
  file: File,
  options: AnnotatePdfOptions,
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  const form = new FormData();
  form.append("file", file);
  form.append("action", options.action);
  if (options.requirements?.trim()) {
    form.append("requirements", options.requirements.trim());
  } else if (options.pattern?.trim()) {
    form.append("pattern", options.pattern.trim());
  }
  return postFormAsync("/v1/pdf/annotate?format=json", form, onProgress);
}

export async function detectSensitivePdf(
  file: File,
  options: {
    action: string;
    entities: string[];
    forceOcr: boolean;
    addTextLayer: boolean;
  },
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  const form = new FormData();
  form.append("file", file);
  form.append("action", options.action);
  form.append("force_ocr", String(options.forceOcr));
  form.append("add_text_layer", String(options.addTextLayer));
  if (options.entities.length) {
    form.append("entities", options.entities.join(","));
  }
  return postFormAsync("/v1/pdf/detect-sensitive?format=json", form, onProgress);
}

export async function structurePdf(
  file: File,
  mode: string,
  forceOcr: boolean,
  onProgress?: (update: ProgressUpdate) => void,
): Promise<JsonRecord> {
  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  form.append("force_ocr", String(forceOcr));
  return postFormAsync("/v1/pdf/structure", form, onProgress);
}

export async function summarizeText(text: string, sentences: number): Promise<JsonRecord> {
  const response = await apiFetch(`${API_BASE}/v1/text/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, sentences }),
  });
  return parseJson(response);
}

export type UnderstandOptions = {
  sentences: number;
  includeSummary: boolean;
  includePii: boolean;
};

export async function understandText(
  text: string,
  options: UnderstandOptions,
): Promise<JsonRecord> {
  const response = await apiFetch(`${API_BASE}/v1/text/understand`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      sentences: options.sentences,
      include_summary: options.includeSummary,
      include_pii: options.includePii,
    }),
  });
  return parseJson(response);
}

export async function understandDocument(
  file: File,
  options: UnderstandOptions,
): Promise<JsonRecord> {
  const form = new FormData();
  form.append("file", file);
  form.append("sentences", String(options.sentences));
  form.append("include_summary", String(options.includeSummary));
  form.append("include_pii", String(options.includePii));
  const response = await apiFetch(`${API_BASE}/v1/documents/understand`, {
    method: "POST",
    body: form,
  });
  return parseJson(response);
}

export type PdfEditorSession = {
  session_id: string;
  filename: string;
  page_count: number;
  pages_edited: number[];
  download_url: string;
};

export type PdfEditorPageState = {
  session_id: string;
  page: number;
  page_count: number;
  text: string;
  preview_url: string;
  pages_edited: number[];
  download_url: string;
  changes_summary?: string;
  edited_text?: string;
};

export async function createPdfEditorSession(file: File): Promise<PdfEditorSession> {
  const form = new FormData();
  form.append("file", file);
  const response = await apiFetch(`${API_BASE}/v1/pdf/editor/session`, {
    method: "POST",
    body: form,
  });
  const payload = await parseJson(response);
  return {
    session_id: String(payload.session_id),
    filename: String(payload.filename ?? file.name),
    page_count: Number(payload.page_count ?? 0),
    pages_edited: Array.isArray(payload.pages_edited) ? payload.pages_edited.map(Number) : [],
    download_url: String(payload.download_url ?? ""),
  };
}

export async function fetchPdfEditorPage(
  sessionId: string,
  pageIndex: number,
): Promise<PdfEditorPageState> {
  const response = await apiFetch(`${API_BASE}/v1/pdf/editor/session/${sessionId}/pages/${pageIndex}`);
  const payload = await parseJson(response);
  return {
    session_id: String(payload.session_id ?? sessionId),
    page: Number(payload.page ?? pageIndex),
    page_count: Number(payload.page_count ?? 0),
    text: String(payload.text ?? ""),
    preview_url: String(payload.preview_url ?? ""),
    pages_edited: Array.isArray(payload.pages_edited) ? payload.pages_edited.map(Number) : [],
    download_url: String(payload.download_url ?? ""),
    changes_summary:
      typeof payload.changes_summary === "string" ? payload.changes_summary : undefined,
    edited_text: typeof payload.edited_text === "string" ? payload.edited_text : undefined,
  };
}

export async function applyPdfEditorEdit(
  sessionId: string,
  pageIndex: number,
  instruction: string,
): Promise<PdfEditorPageState> {
  const form = new FormData();
  form.append("instruction", instruction);
  const response = await apiFetch(
    `${API_BASE}/v1/pdf/editor/session/${sessionId}/pages/${pageIndex}`,
    {
      method: "POST",
      body: form,
    },
  );
  const payload = await parseJson(response);
  return {
    session_id: String(payload.session_id ?? sessionId),
    page: Number(payload.page ?? pageIndex),
    page_count: Number(payload.page_count ?? 0),
    text: String(payload.text ?? ""),
    preview_url: String(payload.preview_url ?? ""),
    pages_edited: Array.isArray(payload.pages_edited) ? payload.pages_edited.map(Number) : [],
    download_url: String(payload.download_url ?? ""),
    changes_summary:
      typeof payload.changes_summary === "string" ? payload.changes_summary : undefined,
    edited_text: typeof payload.edited_text === "string" ? payload.edited_text : undefined,
  };
}

export async function downloadEditorPdf(
  session: PdfEditorSession,
): Promise<{ blobUrl: string; filename: string }> {
  const response = await apiFetch(`${API_BASE}${session.download_url}`);
  if (!response.ok) {
    throw new Error("Edited PDF could not be downloaded.");
  }
  const blob = await response.blob();
  const filename = session.download_url.split("/").pop() || "edited.pdf";
  return { blobUrl: URL.createObjectURL(blob), filename };
}

export type TenantRecord = {
  id: string;
  slug: string;
  name: string;
  is_admin: boolean;
};

export async function fetchTenants(activeSlug?: string): Promise<{
  tenants: TenantRecord[];
  current_tenant: string;
  is_admin: boolean;
}> {
  if (activeSlug) {
    const headers = new Headers();
    headers.set(TENANT_HEADER, activeSlug);
    const response = await fetch(`${API_BASE}/v1/tenants`, { headers });
    const payload = await parseJson(response);
    return {
      tenants: Array.isArray(payload.tenants) ? (payload.tenants as TenantRecord[]) : [],
      current_tenant: String(payload.current_tenant ?? activeSlug),
      is_admin: Boolean(payload.is_admin),
    };
  }
  const response = await apiFetch(`${API_BASE}/v1/tenants`);
  const payload = await parseJson(response);
  return {
    tenants: Array.isArray(payload.tenants) ? (payload.tenants as TenantRecord[]) : [],
    current_tenant: String(payload.current_tenant ?? ""),
    is_admin: Boolean(payload.is_admin),
  };
}

export async function fetchTenantSettings(slug: string): Promise<JsonRecord> {
  const response = await apiFetch(`${API_BASE}/v1/tenants/${slug}/settings`);
  return parseJson(response);
}

export async function updateTenantSettings(slug: string, body: JsonRecord): Promise<JsonRecord> {
  const response = await apiFetch(`${API_BASE}/v1/tenants/${slug}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson(response);
}

export async function fetchLlmModels(
  provider: string,
  baseUrl: string,
): Promise<{ models: string[]; source?: string }> {
  const params = new URLSearchParams({ provider, base_url: baseUrl });
  const response = await apiFetch(`${API_BASE}/v1/tenants/llm/models?${params.toString()}`);
  const payload = await parseJson(response);
  return {
    models: Array.isArray(payload.models) ? payload.models.map(String) : [],
    source: typeof payload.source === "string" ? payload.source : undefined,
  };
}

export async function fetchPiiEntityOptions(): Promise<{ entities: string[] }> {
  const response = await apiFetch(`${API_BASE}/v1/tenants/pii/entities`);
  const payload = await parseJson(response);
  return {
    entities: Array.isArray(payload.entities) ? payload.entities.map(String) : [],
  };
}
