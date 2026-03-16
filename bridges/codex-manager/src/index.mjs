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
    return runCodex(payload, buildProbePrompt(), probeSchema());
  }
  if (action === "create-work-order") {
    return runCodex(payload, buildWorkOrderPrompt(payload), workOrderSchema());
  }
  if (action === "review-attempt") {
    return runCodex(payload, buildReviewPrompt(payload), reviewSchema());
  }
  if (action === "plan-tasks") {
    return runCodex(payload, buildPlanPrompt(payload), taskPlanSchema());
  }
  throw new Error(`Unsupported action: ${action}`);
}

function buildProbePrompt() {
  return `You are a connectivity probe for auto-coder.

Return only JSON matching the schema.
Set backend to "codex".
Do not add explanations.`;
}

async function runCodex(payload, prompt, schema) {
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "auto-coder-codex-"));
  const schemaPath = path.join(tempDir, "schema.json");
  await fs.writeFile(schemaPath, JSON.stringify(schema, null, 2), "utf8");

  try {
    const args = buildArgs(payload, schemaPath);
    const child = spawn("codex", args, {
      cwd: payload.cwd || process.cwd(),
      stdio: ["pipe", "pipe", "pipe"],
      env: process.env,
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.stdin.write(prompt);
    child.stdin.end();

    const exitCode = await new Promise((resolve, reject) => {
      child.on("error", reject);
      child.on("close", resolve);
    });

    const events = parseEvents(stdout);
    const fallbackMessage = extractFinalAgentMessage(events);

    if (exitCode !== 0 && !fallbackMessage) {
      throw new Error(stderr || stdout || `codex exited with code ${exitCode}`);
    }

    let lastMessage = String(fallbackMessage || "").trim();
    try {
      lastMessage = JSON.parse(String(lastMessage));
    } catch {
      // keep plain text
    }
    if (!lastMessage || typeof lastMessage !== "object") {
      throw new Error(`Codex bridge did not produce valid JSON output. stderr=${stderr}`);
    }
    const missingFields = validateRequiredFields(lastMessage, schema);
    if (missingFields.length > 0) {
      throw new Error(`Codex bridge output is missing required fields: ${missingFields.join(", ")}`);
    }
    const threadId = extractThreadId(events) || payload.thread_id || null;

    return {
      ok: true,
      thread_id: threadId,
      result: lastMessage,
      events,
    };
  } finally {
    await fs.rm(tempDir, { recursive: true, force: true });
  }
}

function buildArgs(payload, schemaPath) {
  const reasoningEffort = payload.reasoning_effort || "medium";
  const modelArgs = payload.model ? ["-m", payload.model] : [];
  const configArgs = ["-c", `model_reasoning_effort="${reasoningEffort}"`];
  return [
    "exec",
    ...modelArgs,
    ...configArgs,
    "--skip-git-repo-check",
    "-s",
    "read-only",
    "--output-schema",
    schemaPath,
    "--json",
    "-",
  ];
}

function parseEvents(stdout) {
  return stdout
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return { type: "raw", raw: line };
      }
    });
}

function extractThreadId(events) {
  for (const event of events) {
    if (event.type === "thread.started" && event.thread_id) {
      return event.thread_id;
    }
  }
  return null;
}

function extractFinalAgentMessage(events) {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event.type === "item.completed" && event.item?.type === "agent_message" && event.item?.text) {
      return event.item.text;
    }
  }
  return null;
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
