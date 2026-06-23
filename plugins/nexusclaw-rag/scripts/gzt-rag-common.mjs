import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULTS = Object.freeze({
  apiBaseUrl: "http://127.0.0.1:8000",
  apiPrefix: "/api/v1",
  projectId: 1,
  selectedKbIds: [],
  requestTimeoutMs: 30000,
  sceneRequestTimeoutMs: 90000,
  localRagHealthUrl: "http://127.0.0.1:8101/health"
});

const MODULE_DIR = dirname(fileURLToPath(import.meta.url));
const CONFIG_PATH = resolve(MODULE_DIR, "../config.json");

export function getSettings() {
  try {
    const raw = JSON.parse(readFileSync(CONFIG_PATH, "utf8"));
    return {
      apiBaseUrl: typeof raw.apiBaseUrl === "string" ? raw.apiBaseUrl : DEFAULTS.apiBaseUrl,
      apiPrefix: typeof raw.apiPrefix === "string" ? raw.apiPrefix : DEFAULTS.apiPrefix,
      projectId: Number.isInteger(raw.projectId) ? raw.projectId : DEFAULTS.projectId,
      selectedKbIds: Array.isArray(raw.selectedKbIds)
        ? raw.selectedKbIds.filter((item) => Number.isInteger(item))
        : DEFAULTS.selectedKbIds,
      requestTimeoutMs: Number.isInteger(raw.requestTimeoutMs) ? raw.requestTimeoutMs : DEFAULTS.requestTimeoutMs,
      sceneRequestTimeoutMs: Number.isInteger(raw.sceneRequestTimeoutMs)
        ? raw.sceneRequestTimeoutMs
        : DEFAULTS.sceneRequestTimeoutMs,
      localRagHealthUrl:
        typeof raw.localRagHealthUrl === "string" ? raw.localRagHealthUrl : DEFAULTS.localRagHealthUrl
    };
  } catch {
    return { ...DEFAULTS };
  }
}

function normalizePath(pathname) {
  if (!pathname.startsWith("/")) {
    return `/${pathname}`;
  }
  return pathname;
}

export function buildApiUrl(pathname) {
  const settings = getSettings();
  const prefix = settings.apiPrefix.replace(/\/$/, "");
  const path = normalizePath(pathname);
  return `${settings.apiBaseUrl}${prefix}${path}`;
}

export async function requestJson(url, options = {}, timeoutMs = DEFAULTS.requestTimeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      },
      signal: controller.signal
    });

    const text = await response.text();
    let payload = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = { raw: text };
      }
    }

    if (!response.ok) {
      const detail = payload && typeof payload === "object" ? JSON.stringify(payload) : text;
      throw new Error(`http_${response.status}: ${detail}`);
    }
    return payload;
  } finally {
    clearTimeout(timeout);
  }
}

function pickSelectedKbIds(inputKbIds) {
  if (Array.isArray(inputKbIds) && inputKbIds.length > 0) {
    return inputKbIds;
  }
  return getSettings().selectedKbIds;
}

export async function ragSearch({ query, selected_kb_ids = [] }) {
  const settings = getSettings();
  if (!query || !String(query).trim()) {
    throw new Error("query_required");
  }
  return requestJson(
    buildApiUrl(`/projects/${settings.projectId}/search`),
    {
      method: "POST",
      body: JSON.stringify({
        query: String(query).trim(),
        selected_kb_ids: pickSelectedKbIds(selected_kb_ids)
      })
    },
    settings.requestTimeoutMs
  );
}

export async function ragAsk({
  query,
  session_id = null,
  use_memory = true,
  selected_kb_ids = [],
  source = "openclaw"
}) {
  const settings = getSettings();
  if (!query || !String(query).trim()) {
    throw new Error("query_required");
  }
  return requestJson(
    buildApiUrl(`/projects/${settings.projectId}/chat/ask`),
    {
      method: "POST",
      body: JSON.stringify({
        session_id,
        query: String(query).trim(),
        use_memory,
        selected_kb_ids: pickSelectedKbIds(selected_kb_ids),
        source,
        switches: {
          retrieval_filter: true
        }
      })
    },
    settings.requestTimeoutMs
  );
}

export async function ragHealth() {
  const settings = getSettings();
  const [api, rag] = await Promise.allSettled([
    requestJson(`${settings.apiBaseUrl}/health`, { method: "GET", headers: {} }, settings.requestTimeoutMs),
    requestJson(settings.localRagHealthUrl, { method: "GET", headers: {} }, settings.requestTimeoutMs)
  ]);

  return {
    api: api.status === "fulfilled" ? api.value : { status: "error", error: String(api.reason) },
    local_rag: rag.status === "fulfilled" ? rag.value : { status: "error", error: String(rag.reason) },
    settings
  };
}
