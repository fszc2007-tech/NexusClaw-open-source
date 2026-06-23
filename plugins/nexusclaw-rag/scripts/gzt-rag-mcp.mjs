#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  McpError,
  ErrorCode
} from "@modelcontextprotocol/sdk/types.js";

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

const TOOL_DEFINITIONS = [
  {
    name: "gzt_rag_search",
    description: "Search the NexusClaw knowledge base and return ranked hits with snippets.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "The user's search query." },
        selected_kb_ids: {
          type: "array",
          items: { type: "integer" },
          description: "Optional knowledge base IDs to restrict retrieval."
        }
      },
      required: ["query"]
    }
  },
  {
    name: "gzt_rag_ask",
    description: "Ask the NexusClaw grounded Q&A API and return answer, sources, and retrieval status.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "The user's natural-language question." },
        session_id: {
          type: "string",
          description: "Optional backend session ID for multi-turn memory."
        },
        use_memory: {
          type: "boolean",
          description: "Whether the backend should use memory for this turn."
        },
        selected_kb_ids: {
          type: "array",
          items: { type: "integer" },
          description: "Optional knowledge base IDs to restrict retrieval."
        }
      },
      required: ["query"]
    }
  },
  {
    name: "gzt_rag_health",
    description: "Check both the NexusClaw API and the local RAG health endpoints.",
    inputSchema: {
      type: "object",
      properties: {}
    }
  },
  {
    name: "gzt_scene_continue",
    description: "Continue a workflow turn through the NexusClaw chat entry and require a scene response.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "The user's workflow instruction or field answer." },
        session_id: { type: "string", description: "Optional backend chat session ID." },
        use_memory: { type: "boolean", description: "Whether to reuse chat memory while continuing the case." },
        selected_kb_ids: {
          type: "array",
          items: { type: "integer" },
          description: "Optional knowledge base IDs."
        },
        source: { type: "string", description: "Caller label, defaults to openclaw." }
      },
      required: ["query"]
    }
  },
  {
    name: "gzt_scene_start",
    description: "Explicitly start or resume a NexusClaw workflow case.",
    inputSchema: {
      type: "object",
      properties: {
        scene_key: { type: "string", description: "Scene identifier. Defaults to hk_tax_address_change." },
        route_key: { type: "string", description: "Optional route, such as ir1249 or irc3111a." },
        session_id: { type: "string", description: "Optional backend chat session ID to reuse." },
        initial_query: { type: "string", description: "Optional original user goal." },
        selected_kb_ids: {
          type: "array",
          items: { type: "integer" },
          description: "Optional knowledge base IDs."
        },
        switches: { type: "object", description: "Optional backend switches." },
        resume_if_exists: { type: "boolean", description: "Whether to reuse an active case if found." },
        source: { type: "string", description: "Caller label, defaults to openclaw." }
      },
      required: []
    }
  },
  {
    name: "gzt_scene_status",
    description: "Get the current workflow scene status, missing fields, next actions, and artifacts.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." }
      },
      required: ["case_id"]
    }
  },
  {
    name: "gzt_scene_get_fields",
    description: "Get collected, missing, pending-confirmation, and visible workflow fields for a case.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." }
      },
      required: ["case_id"]
    }
  },
  {
    name: "gzt_scene_get_next_actions",
    description: "Get the allowed next actions, blocking reason, and next question for a case.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." }
      },
      required: ["case_id"]
    }
  },
  {
    name: "gzt_scene_collect_info",
    description: "Merge structured field values into a workflow case.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." },
        payload: { type: "object", description: "Structured field values to merge." },
        source: { type: "string", description: "Caller label, defaults to openclaw." }
      },
      required: ["case_id", "payload"]
    }
  },
  {
    name: "gzt_scene_update_field",
    description: "Set or clear a single workflow field on a case.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." },
        field_name: { type: "string", description: "Field name to update." },
        value: { description: "Field value. Use null or empty string to clear it." },
        source: { type: "string", description: "Caller label, defaults to openclaw." }
      },
      required: ["case_id", "field_name"]
    }
  },
  {
    name: "gzt_scene_confirm_payload",
    description: "Confirm the collected payload before PDF generation.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." },
        confirmation_token: { type: "string", description: "Required confirmation token from scene status for gated actions." }
      },
      required: ["case_id"]
    }
  },
  {
    name: "gzt_scene_generate_pdf",
    description: "Generate the workflow PDF artifacts for a case.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." }
      },
      required: ["case_id"]
    }
  },
  {
    name: "gzt_scene_confirm_signature",
    description: "Confirm that the user has signed the generated PDF.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." },
        confirmation_token: { type: "string", description: "Required confirmation token from scene status for gated actions." }
      },
      required: ["case_id"]
    }
  },
  {
    name: "gzt_scene_preview_mail",
    description: "Build the workflow mail preview for a case.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." }
      },
      required: ["case_id"]
    }
  },
  {
    name: "gzt_scene_send_mail",
    description: "Send the prepared workflow mail when the backend allows it.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." },
        confirmation_token: { type: "string", description: "Required confirmation token from scene status for gated actions." }
      },
      required: ["case_id"]
    }
  },
  {
    name: "gzt_scene_get_artifact",
    description: "Get the artifact URL for a generated preview or final PDF.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." },
        artifact_key: { type: "string", description: "Artifact key, such as preview_pdf or final_pdf." }
      },
      required: ["case_id", "artifact_key"]
    }
  },
  {
    name: "gzt_scene_recover",
    description: "Refresh or auto-recover a workflow case after a runtime failure such as stale confirmation tokens or missing generated artifacts.",
    inputSchema: {
      type: "object",
      properties: {
        case_id: { type: "string", description: "Scene case ID." },
        strategy: {
          type: "string",
          description: "Recovery strategy: auto, retry, refresh, generate_pdf, or preview_mail."
        },
        source: { type: "string", description: "Caller label, defaults to openclaw." }
      },
      required: ["case_id"]
    }
  }
];

const ACTION_TOOL_MAP = {
  gzt_scene_confirm_payload: "confirm_payload",
  gzt_scene_generate_pdf: "generate_pdf",
  gzt_scene_confirm_signature: "confirm_signature",
  gzt_scene_preview_mail: "preview_mail",
  gzt_scene_send_mail: "send_mail"
};

function asObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value;
}

function textResult(payload) {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(payload, null, 2)
      }
    ]
  };
}

const server = new Server(
  {
    name: "nexusclaw-rag",
    version: "0.2.0"
  },
  {
    capabilities: {
      tools: {}
    }
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOL_DEFINITIONS
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const name = request.params.name;
  const args = asObject(request.params.arguments);

  try {
    if (name === "gzt_rag_search") {
      return textResult(await ragSearch(args));
    }
    if (name === "gzt_rag_ask") {
      return textResult(await ragAsk(args));
    }
    if (name === "gzt_rag_health") {
      return textResult(await ragHealth());
    }
    if (name === "gzt_scene_continue") {
      return textResult(await sceneContinue(args));
    }
    if (name === "gzt_scene_start") {
      return textResult(await sceneStart(args));
    }
    if (name === "gzt_scene_status") {
      return textResult(await sceneStatus(args));
    }
    if (name === "gzt_scene_get_fields") {
      return textResult(await sceneGetFields(args));
    }
    if (name === "gzt_scene_get_next_actions") {
      return textResult(await sceneGetNextActions(args));
    }
    if (name === "gzt_scene_collect_info") {
      return textResult(await sceneCollectInfo(args));
    }
    if (name === "gzt_scene_update_field") {
      return textResult(await sceneUpdateField(args));
    }
    if (name === "gzt_scene_get_artifact") {
      return textResult(await sceneGetArtifact(args));
    }
    if (name === "gzt_scene_recover") {
      return textResult(await sceneRecover(args));
    }
    if (ACTION_TOOL_MAP[name]) {
      return textResult(
        await sceneAction({
          case_id: args.case_id,
          action_name: ACTION_TOOL_MAP[name],
          confirmation_token: args.confirmation_token
        })
      );
    }
  } catch (error) {
    return {
      isError: true,
      content: [
        {
          type: "text",
          text: JSON.stringify(
            {
              error: String(error && error.message ? error.message : error)
            },
            null,
            2
          )
        }
      ]
    };
  }

  throw new McpError(ErrorCode.MethodNotFound, `unknown_tool: ${name}`);
});

const transport = new StdioServerTransport();
await server.connect(transport);
