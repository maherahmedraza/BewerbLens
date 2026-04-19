import "server-only";

import { dashboardEnv } from "@/lib/env";

type TriggeredBy = "manual" | "backfill" | "incremental" | "scheduler";

interface TriggerPipelineRunParams {
  userId: string;
  triggeredBy: TriggeredBy;
  sinceDate?: string;
}

interface OrchestratorErrorPayload {
  detail?: string;
}

export async function triggerPipelineRun({
  userId,
  triggeredBy,
  sinceDate,
}: TriggerPipelineRunParams) {
  const response = await fetch(`${dashboardEnv.orchestratorUrl}/runs/trigger`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_id: userId,
      triggered_by: triggeredBy,
      since_date: sinceDate,
    }),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as OrchestratorErrorPayload;
    throw new Error(payload.detail || "Failed to trigger sync run.");
  }

  return response.json();
}
