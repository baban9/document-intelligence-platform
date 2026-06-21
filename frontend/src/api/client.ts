const API_BASE = import.meta.env.VITE_API_BASE ?? "";

type JsonRecord = Record<string, unknown>;

export type { JsonRecord };

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
  const response = await fetch(`${API_BASE}${path}${separator}async=true`, {
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
  const response = await fetch(`${API_BASE}${path}?async=true`, {
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

  const response = await fetch(`${API_BASE}${downloadPath}`);
  if (!response.ok) {
    throw new Error("Processed PDF could not be downloaded.");
  }
  const blob = await response.blob();
  const filename = downloadPath.split("/").pop() || fallbackName;
  return { blobUrl: URL.createObjectURL(blob), filename };
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
    const response = await fetch(`${API_BASE}${pollUrl}`);
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

  const response = await fetch(`${API_BASE}/v1/documents/process?async=true`, {
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
  const response = await fetch(`${API_BASE}/v1/documents/identify`, {
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
  const response = await fetch(`${API_BASE}/v1/text/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, sentences }),
  });
  return parseJson(response);
}
