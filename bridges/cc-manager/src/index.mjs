import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";

const [action, payloadPath] = process.argv.slice(2);

if (!action || !payloadPath) {
  console.error("Usage: node src/index.mjs <action> <payload.json>");
  process.exit(2);
}

const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));

try {
  const result = await runAction(action, payload);
  process.stdout.write(JSON.stringify(result));
} catch (error) {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
}

async function runAction(action, payload) {
  if (action === "probe-live") {
    return runCc(payload, buildProbePrompt(), probeSchema());
  }
  if (action === "create-work-order") {
    return runCc(payload, buildWorkOrderPrompt(payload), workOrderSchema());
  }
  if (action === "review-attempt") {
    return runCc(payload, buildReviewPrompt(payload), reviewSchema());
  }
  if (action === "plan-tasks") {
    return runCc(payload, buildPlanPrompt(payload), taskPlanSchema());
  }
  throw new Error(`Unsupported action: ${action}`);
}

function buildProbePrompt() {
  return `You are the manager backend for auto-coder.

Return only JSON matching the schema.
Set backend to "cc".
Do not add explanations.`;
}

async function runCc(payload, prompt, schema) {
  // Claude Code doesn't have --output-schema, so we inject schema into system prompt
  const systemPrompt = `You are the manager backend for auto-coder.
Return ONLY valid JSON matching this schema, no markdown, no explanation:
${JSON.stringify(schema, null, 2)}`;

  const modelArgs = payload.model ? ["--model", payload.model] : [];

  const args = [
    "-p", prompt,
    "--system-prompt", systemPrompt,
    "--output-format", "json",
    "--tools", "",
    "--permission-mode", "bypassPermissions",
    "--no-session-persistence",
    ...modelArgs,
  ];

  // Claude Code refuses to run inside another Claude Code session (sets CLAUDECODE env var).
  // Remove it before spawning.
  const env = { ...process.env };
  delete env.CLAUDECODE;

  const child = spawn("claude", args, {
    cwd: payload.cwd || process.cwd(),
    stdio: ["pipe", "pipe", "pipe"],
    env,
  });

  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (chunk) => {
    stdout += chunk.toString();
  });
  child.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });
  // Close stdin since we're using -p mode (prompt from CLI, not from stdin)
  child.stdin.end();

  const exitCode = await new Promise((resolve, reject) => {
    child.on("error", reject);
    child.on("close", resolve);
  });

  if (exitCode !== 0) {
    throw new Error(stderr || stdout || `claude exited with code ${exitCode}`);
  }

  // Claude Code --output-format json returns: {result: "<text>", type: "result", subtype: "success", ...}
  // The <text> contains the actual JSON response from the model.
  let parsed;
  try {
    parsed = JSON.parse(stdout.trim());
  } catch {
    throw new Error(`cc bridge did not return valid JSON. stdout=${stdout}`);
  }

  if (!parsed.result || typeof parsed.result !== "string") {
    throw new Error(`cc bridge output missing 'result' field. parsed=${JSON.stringify(parsed)}`);
  }

  let lastMessage;
  try {
    lastMessage = JSON.parse(parsed.result);
  } catch {
    throw new Error(`cc bridge result is not valid JSON. result=${parsed.result}`);
  }

  if (!lastMessage || typeof lastMessage !== "object") {
    throw new Error(`cc bridge did not produce valid JSON object. result=${parsed.result}`);
  }

  const missingFields = validateRequiredFields(lastMessage, schema);
  if (missingFields.length > 0) {
    throw new Error(`cc bridge output is missing required fields: ${missingFields.join(", ")}`);
  }

  // Claude Code doesn't have thread_id like codex, but we accept it from payload if provided
  const threadId = payload.thread_id || null;

  return {
    ok: true,
    thread_id: threadId,
    result: lastMessage,
    events: [], // Claude Code json output doesn't have events like codex NDJSON
  };
}

function validateRequiredFields(payload, schema) {
  const required = Array.isArray(schema.required) ? schema.required : [];
  const missing = [];
  for (const field of required) {
    if (!(field in payload)) {
      missing.push(field);
    }
  }
  return missing;
}

function buildWorkOrderPrompt(payload) {
  const { task, history = [] } = payload;
  return `You are the manager backend for auto-coder.

Create the next small executable work order for this task.
Return only JSON matching the provided schema.

TASK:
${JSON.stringify(task, null, 2)}

HISTORY:
${JSON.stringify(history, null, 2)}

Rules:
- keep the work order small and executable in one tick
- keep allowed_paths inside the task contract
- preserve completion_commands unless you have a strong reason to narrow them
- selected_worker should be one of the task preferred workers when possible
- manager_feedback should be concise and actionable`;
}

function buildReviewPrompt(payload) {
  const { task, work_order, attempt_context, history = [] } = payload;
  return `You are the manager backend for auto-coder.

Review the attempt and decide approve, retry, or abandon.
Return only JSON matching the provided schema.

TASK:
${JSON.stringify(task, null, 2)}

WORK_ORDER:
${JSON.stringify(work_order, null, 2)}

ATTEMPT:
${JSON.stringify(attempt_context, null, 2)}

HISTORY:
${JSON.stringify(history, null, 2)}

Rules:
- approve only if the attempt appears complete and correct
- retry if the problem is fixable in another attempt
- abandon only if the task should be blocked
- blockers must be short machine-readable strings
- if verdict is retry, include a next_work_order object
- otherwise set next_work_order to null`;
}

function buildPlanPrompt(payload) {
  return `You are the planning backend for auto-coder.

Generate an execution-ready backlog and return only JSON matching the schema.

ROADMAP:
${payload.roadmap}

PROJECT:
${payload.project_context}

PLANNING HINTS:
${payload.planning_hints || "(none)"}

CONSTRAINTS:
${payload.constraints || "(none)"}

ARCHITECTURE NOTES:
${payload.architecture_notes || "(none)"}

Rules:
- every task must have explicit depends_on, allowed_paths, baseline_commands, completion_commands, acceptance_criteria
- tasks must be small enough for 1-3 work orders
- respect planning hints when they define repo-specific command, naming, or API conventions
- keep ids stable and slug-like
- output only JSON`;
}

function workOrderSchema() {
  return {
    type: "object",
    additionalProperties: false,
    required: ["goal", "scope_summary", "allowed_paths", "completion_commands", "selected_worker", "manager_feedback"],
    properties: {
      goal: { type: "string" },
      scope_summary: { type: "string" },
      allowed_paths: { type: "array", items: { type: "string" } },
      completion_commands: { type: "array", items: { type: "string" } },
      selected_worker: { type: "string" },
      manager_feedback: { type: "string" }
    }
  };
}

function probeSchema() {
  return {
    type: "object",
    additionalProperties: false,
    required: ["status", "backend"],
    properties: {
      status: { type: "string", enum: ["ok"] },
      backend: { type: "string" }
    }
  };
}

function reviewSchema() {
  return {
    type: "object",
    additionalProperties: false,
    required: ["verdict", "feedback", "blockers", "next_work_order"],
    properties: {
      verdict: { type: "string", enum: ["approve", "retry", "abandon"] },
      feedback: { type: "string" },
      blockers: { type: "array", items: { type: "string" } },
      next_work_order: {
        anyOf: [
          { type: "null" },
          {
            type: "object",
            additionalProperties: false,
            required: ["goal", "scope_summary", "allowed_paths", "completion_commands", "selected_worker", "manager_feedback"],
            properties: {
              goal: { type: "string" },
              scope_summary: { type: "string" },
              allowed_paths: { type: "array", items: { type: "string" } },
              completion_commands: { type: "array", items: { type: "string" } },
              selected_worker: { type: "string" },
              manager_feedback: { type: "string" }
            }
          }
        ]
      }
    }
  };
}

function taskPlanSchema() {
  return {
    type: "object",
    additionalProperties: false,
    required: ["tasks"],
    properties: {
      tasks: {
        type: "array",
        items: {
          type: "object",
          additionalProperties: false,
          required: [
            "id",
            "title",
            "depends_on",
            "allowed_paths",
            "baseline_commands",
            "completion_commands",
            "acceptance_criteria",
            "prompt"
          ],
          properties: {
            id: { type: "string" },
            title: { type: "string" },
            depends_on: { type: "array", items: { type: "string" } },
            allowed_paths: { type: "array", items: { type: "string" } },
            baseline_commands: { type: "array", items: { type: "string" } },
            completion_commands: { type: "array", items: { type: "string" } },
            acceptance_criteria: { type: "array", items: { type: "string" } },
            prompt: { type: "string" }
          }
        }
      }
    }
  };
}
