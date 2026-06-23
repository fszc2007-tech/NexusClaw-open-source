import { buildApiUrl, getSettings, requestJson } from "./gzt-rag-common.mjs";

function normalizeActionName(actionName) {
  return String(actionName || "").trim();
}

function pickSessionId(sessionId) {
  if (!sessionId) {
    return null;
  }
  const normalized = String(sessionId).trim();
  return normalized || null;
}

function pickSceneKey(sceneKey) {
  const normalized = String(sceneKey || "").trim();
  return normalized || "hk_tax_address_change";
}

function pickSource(source) {
  const normalized = String(source || "").trim();
  return normalized || "openclaw";
}

function getSceneTimeoutMs(settings) {
  if (Number.isInteger(settings.sceneRequestTimeoutMs) && settings.sceneRequestTimeoutMs > 0) {
    return settings.sceneRequestTimeoutMs;
  }
  return settings.requestTimeoutMs;
}

function unwrapData(payload) {
  if (payload && typeof payload === "object" && "data" in payload) {
    return payload.data;
  }
  return payload;
}

export async function sceneContinue({
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
  const payload = await requestJson(
    buildApiUrl(`/projects/${settings.projectId}/chat/ask`),
    {
      method: "POST",
      body: JSON.stringify({
        session_id: pickSessionId(session_id),
        query: String(query).trim(),
        use_memory,
        selected_kb_ids: Array.isArray(selected_kb_ids) ? selected_kb_ids : [],
        source: pickSource(source),
        switches: {
          retrieval_filter: true
        }
      })
    },
    getSceneTimeoutMs(settings)
  );
  const data = unwrapData(payload);
  if (!data || data.response_mode !== "scene") {
    throw new Error("scene_not_triggered");
  }
  return {
    ...payload,
    data: {
      ...data,
      scene_runtime: {
        scene: data.scene || null,
        field_status: data.field_status || null,
        next_actions: data.next_actions || null,
        planner: ((data.next_actions || {}).planner) || (((data.scene || {}).runtime || {}).planner) || null,
        intent_mode: data.intent_mode || "scene_request",
        classification_reason: data.classification_reason || null,
        hybrid_context: data.hybrid_context || null
      }
    }
  };
}

export async function sceneStart({
  scene_key = "hk_tax_address_change",
  route_key = null,
  session_id = null,
  initial_query = null,
  selected_kb_ids = [],
  switches = {},
  resume_if_exists = true,
  source = "openclaw"
}) {
  const settings = getSettings();
  return requestJson(
    buildApiUrl(`/projects/${settings.projectId}/scenes/start`),
    {
      method: "POST",
      body: JSON.stringify({
        scene_key: pickSceneKey(scene_key),
        route_key,
        session_id: pickSessionId(session_id),
        source: pickSource(source),
        initial_query,
        selected_kb_ids: Array.isArray(selected_kb_ids) ? selected_kb_ids : [],
        switches: switches && typeof switches === "object" ? switches : {},
        resume_if_exists: resume_if_exists !== false
      })
    },
    getSceneTimeoutMs(settings)
  );
}

export async function sceneStatus({ case_id }) {
  const settings = getSettings();
  if (!case_id || !String(case_id).trim()) {
    throw new Error("case_id_required");
  }
  return requestJson(
    buildApiUrl(`/projects/${settings.projectId}/scenes/${String(case_id).trim()}`),
    {
      method: "GET",
      headers: {}
    },
    getSceneTimeoutMs(settings)
  );
}

export async function sceneGetFields({ case_id }) {
  const settings = getSettings();
  if (!case_id || !String(case_id).trim()) {
    throw new Error("case_id_required");
  }
  return requestJson(
    buildApiUrl(`/projects/${settings.projectId}/scenes/${String(case_id).trim()}/fields`),
    {
      method: "GET",
      headers: {}
    },
    getSceneTimeoutMs(settings)
  );
}

export async function sceneGetNextActions({ case_id }) {
  const settings = getSettings();
  if (!case_id || !String(case_id).trim()) {
    throw new Error("case_id_required");
  }
  return requestJson(
    buildApiUrl(`/projects/${settings.projectId}/scenes/${String(case_id).trim()}/next-actions`),
    {
      method: "GET",
      headers: {}
    },
    getSceneTimeoutMs(settings)
  );
}

export async function sceneCollectInfo({ case_id, payload = {}, source = "openclaw" }) {
  const settings = getSettings();
  if (!case_id || !String(case_id).trim()) {
    throw new Error("case_id_required");
  }
  return requestJson(
    buildApiUrl(`/projects/${settings.projectId}/scenes/${String(case_id).trim()}/payload`),
    {
      method: "PATCH",
      body: JSON.stringify({
        payload: payload && typeof payload === "object" ? payload : {},
        source: pickSource(source),
        merge_mode: "merge"
      })
    },
    getSceneTimeoutMs(settings)
  );
}

export async function sceneUpdateField({ case_id, field_name, value, source = "openclaw" }) {
  const settings = getSettings();
  if (!case_id || !String(case_id).trim()) {
    throw new Error("case_id_required");
  }
  if (!field_name || !String(field_name).trim()) {
    throw new Error("field_name_required");
  }
  return requestJson(
    buildApiUrl(`/projects/${settings.projectId}/scenes/${String(case_id).trim()}/fields/${String(field_name).trim()}`),
    {
      method: "PATCH",
      body: JSON.stringify({
        value,
        source: pickSource(source)
      })
    },
    getSceneTimeoutMs(settings)
  );
}

export async function sceneAction({ case_id, action_name, confirmation_token = null }) {
  const settings = getSettings();
  if (!case_id || !String(case_id).trim()) {
    throw new Error("case_id_required");
  }
  const normalizedAction = normalizeActionName(action_name);
  if (!normalizedAction) {
    throw new Error("action_name_required");
  }
  return requestJson(
    buildApiUrl(`/projects/${settings.projectId}/scenes/${String(case_id).trim()}/actions/${normalizedAction}`),
    {
      method: "POST",
      body: JSON.stringify({
        confirmation_token: confirmation_token ? String(confirmation_token).trim() : null
      })
    },
    getSceneTimeoutMs(settings)
  );
}

export async function sceneGetArtifact({ case_id, artifact_key }) {
  if (!case_id || !String(case_id).trim()) {
    throw new Error("case_id_required");
  }
  if (!artifact_key || !String(artifact_key).trim()) {
    throw new Error("artifact_key_required");
  }
  const settings = getSettings();
  const normalizedCaseId = String(case_id).trim();
  const key = String(artifact_key).trim();
  const scenePayload = unwrapData(await sceneStatus({ case_id: normalizedCaseId })) || {};
  const pdfPreviewPanel = (((scenePayload.panels || {}).pdf_preview) || {});
  const artifactUrlMap = {
    preview_pdf: pdfPreviewPanel.preview_url ? buildApiUrl(pdfPreviewPanel.preview_url.replace(/^\/api\/v1/, "")) : null,
    final_pdf: pdfPreviewPanel.final_url ? buildApiUrl(pdfPreviewPanel.final_url.replace(/^\/api\/v1/, "")) : null
  };
  const relativeUrl = artifactUrlMap[key]
    || buildApiUrl(`/projects/${settings.projectId}/scenes/${normalizedCaseId}/artifacts/${key}`);
  return {
    case_id: normalizedCaseId,
    artifact_key: key,
    scene_state: scenePayload.state || null,
    available_artifacts: pdfPreviewPanel,
    url: relativeUrl
  };
}

export async function sceneRecover({ case_id, strategy = "auto", source = "openclaw" }) {
  const settings = getSettings();
  if (!case_id || !String(case_id).trim()) {
    throw new Error("case_id_required");
  }
  return requestJson(
    buildApiUrl(`/projects/${settings.projectId}/scenes/${String(case_id).trim()}/recover`),
    {
      method: "POST",
      body: JSON.stringify({
        strategy: strategy ? String(strategy).trim() : "auto",
        source: pickSource(source)
      })
    },
    getSceneTimeoutMs(settings)
  );
}
