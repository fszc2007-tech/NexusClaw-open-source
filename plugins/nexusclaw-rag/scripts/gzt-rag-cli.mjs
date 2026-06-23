#!/usr/bin/env node

import { ragAsk, ragHealth, ragSearch } from "./gzt-rag-common.mjs";
import {
  sceneAction,
  sceneCollectInfo,
  sceneContinue,
  sceneGetArtifact,
  sceneGetFields,
  sceneGetNextActions,
  sceneRecover,
  sceneStart,
  sceneStatus,
  sceneUpdateField
} from "./gzt-scene-common.mjs";

function parseArgs(argv) {
  const args = { _: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (!current.startsWith("--")) {
      args._.push(current);
      continue;
    }
    const key = current.slice(2);
    const next = argv[index + 1];
    if (next && !next.startsWith("--")) {
      args[key] = next;
      index += 1;
      continue;
    }
    args[key] = true;
  }
  return args;
}

function parseSelectedKbIds(value) {
  if (!value) {
    return [];
  }
  return String(value)
    .split(",")
    .map((item) => Number.parseInt(item.trim(), 10))
    .filter((item) => !Number.isNaN(item));
}

function parseBoolean(value, defaultValue = true) {
  if (value === undefined) {
    return defaultValue;
  }
  if (typeof value === "boolean") {
    return value;
  }
  const normalized = String(value).trim().toLowerCase();
  if (["true", "1", "yes", "y"].includes(normalized)) {
    return true;
  }
  if (["false", "0", "no", "n"].includes(normalized)) {
    return false;
  }
  return defaultValue;
}

function parseJson(value, fallback = {}) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  if (typeof value === "object") {
    return value;
  }
  try {
    return JSON.parse(String(value));
  } catch (error) {
    throw new Error(`invalid_json: ${String(error && error.message ? error.message : error)}`);
  }
}

function parseMaybeJson(value) {
  if (value === undefined) {
    return undefined;
  }
  try {
    return JSON.parse(String(value));
  } catch {
    return value;
  }
}

function usage() {
  return [
    "usage: gzt-rag-cli.mjs <command> [options]",
    "",
    "rag commands:",
    "  search --query <text> [--selected-kb-ids 1,2]",
    "  ask --query <text> [--session-id <id>] [--use-memory true|false] [--selected-kb-ids 1,2]",
    "  health",
    "",
    "scene commands:",
    "  scene-start [--scene-key <key>] [--route-key <key>] [--session-id <id>] [--initial-query <text>]",
    "              [--selected-kb-ids 1,2] [--switches '{\"retrieval_filter\":true}'] [--resume-if-exists true|false]",
    "  scene-continue --query <text> [--session-id <id>] [--use-memory true|false] [--selected-kb-ids 1,2]",
    "  scene-status --case-id <id>",
    "  scene-fields --case-id <id>",
    "  scene-next-actions --case-id <id>",
    "  scene-collect --case-id <id> --payload '{\"field\":\"value\"}'",
    "  scene-update-field --case-id <id> --field-name <name> [--value '...']",
    "  scene-recover --case-id <id> [--strategy auto|retry|refresh|generate_pdf|preview_mail]",
    "  scene-action --case-id <id> --action-name <confirm_payload|generate_pdf|confirm_signature|preview_mail|send_mail> [--confirmation-token <token>]",
    "  scene-artifact --case-id <id> --artifact-key <preview_pdf|final_pdf>"
  ].join("\n");
}

async function main() {
  const [, , command, ...rest] = process.argv;
  const args = parseArgs(rest);

  let result;
  if (command === "search") {
    result = await ragSearch({
      query: args.query || args.q,
      selected_kb_ids: parseSelectedKbIds(args["selected-kb-ids"])
    });
  } else if (command === "ask") {
    result = await ragAsk({
      query: args.query || args.q,
      session_id: args["session-id"] || null,
      use_memory: parseBoolean(args["use-memory"], true),
      selected_kb_ids: parseSelectedKbIds(args["selected-kb-ids"])
    });
  } else if (command === "health") {
    result = await ragHealth();
  } else if (command === "scene-start") {
    result = await sceneStart({
      scene_key: args["scene-key"] || args.scene_key,
      route_key: args["route-key"] || args.route_key || null,
      session_id: args["session-id"] || args.session_id || null,
      initial_query: args["initial-query"] || args.initial_query || null,
      selected_kb_ids: parseSelectedKbIds(args["selected-kb-ids"] || args.selected_kb_ids),
      switches: parseJson(args.switches, {}),
      resume_if_exists: parseBoolean(args["resume-if-exists"], true),
      source: args.source || "openclaw"
    });
  } else if (command === "scene-continue") {
    result = await sceneContinue({
      query: args.query || args.q,
      session_id: args["session-id"] || args.session_id || null,
      use_memory: parseBoolean(args["use-memory"], true),
      selected_kb_ids: parseSelectedKbIds(args["selected-kb-ids"] || args.selected_kb_ids),
      source: args.source || "openclaw"
    });
  } else if (command === "scene-status") {
    result = await sceneStatus({
      case_id: args["case-id"] || args.case_id
    });
  } else if (command === "scene-fields") {
    result = await sceneGetFields({
      case_id: args["case-id"] || args.case_id
    });
  } else if (command === "scene-next-actions") {
    result = await sceneGetNextActions({
      case_id: args["case-id"] || args.case_id
    });
  } else if (command === "scene-collect") {
    result = await sceneCollectInfo({
      case_id: args["case-id"] || args.case_id,
      payload: parseJson(args.payload, {}),
      source: args.source || "openclaw"
    });
  } else if (command === "scene-update-field") {
    result = await sceneUpdateField({
      case_id: args["case-id"] || args.case_id,
      field_name: args["field-name"] || args.field_name,
      value: parseMaybeJson(args.value),
      source: args.source || "openclaw"
    });
  } else if (command === "scene-recover") {
    result = await sceneRecover({
      case_id: args["case-id"] || args.case_id,
      strategy: args.strategy || "auto",
      source: args.source || "openclaw"
    });
  } else if (command === "scene-action") {
    result = await sceneAction({
      case_id: args["case-id"] || args.case_id,
      action_name: args["action-name"] || args.action_name,
      confirmation_token: args["confirmation-token"] || args.confirmation_token || null
    });
  } else if (command === "scene-artifact") {
    result = await sceneGetArtifact({
      case_id: args["case-id"] || args.case_id,
      artifact_key: args["artifact-key"] || args.artifact_key
    });
  } else {
    throw new Error(usage());
  }

  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${String(error && error.stack ? error.stack : error)}\n`);
  process.exitCode = 1;
});
