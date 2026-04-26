import "server-only";

type TriggeredBy = "manual" | "backfill" | "incremental" | "scheduler";

interface TriggerPipelineRunParams {
  userId: string;
  triggeredBy: TriggeredBy;
  sinceDate?: string;
}

interface OrchestratorErrorPayload {
  detail?: string;
  error?: string;
}

function getOrchestratorUrl() {
  return process.env.ORCHESTRATOR_URL || process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8000";
}

function getOrchestratorApiKey() {
  const apiKey = process.env.ORCHESTRATOR_API_KEY;
  if (!apiKey) {
    throw new Error("Missing required environment variable: ORCHESTRATOR_API_KEY");
  }
  return apiKey;
}

async function parseOrchestratorError(response: Response) {
  const payload = (await response.json().catch(() => ({}))) as OrchestratorErrorPayload;
  return payload.detail || payload.error || "Request to orchestrator failed.";
}

export async function orchestratorRequest<T>(
  path: string,
  init: RequestInit = {},
  userId?: string
) {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  headers.set("x-orchestrator-api-key", getOrchestratorApiKey());
  if (userId) {
    headers.set("x-bewerblens-user-id", userId);
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const response = await fetch(`${getOrchestratorUrl()}${normalizedPath}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await parseOrchestratorError(response));
  }

  if (response.status === 204) {
    return null as T;
  }

  return (await response.json()) as T;
}

export async function triggerPipelineRun({
  userId,
  triggeredBy,
  sinceDate,
}: TriggerPipelineRunParams) {
  return orchestratorRequest(
    "/runs/trigger",
    {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        triggered_by: triggeredBy,
        since_date: sinceDate,
      }),
    },
    userId
  );
}
