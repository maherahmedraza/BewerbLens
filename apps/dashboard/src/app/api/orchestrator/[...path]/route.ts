import { NextResponse } from "next/server";

import { orchestratorRequest } from "@/lib/server/orchestrator";
import { createClient } from "@/lib/supabase/server";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

function isUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

async function getAuthenticatedUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return { supabase, user: null };
  }

  return { supabase, user };
}

async function verifyRunOwnership(supabase: Awaited<ReturnType<typeof createClient>>, runId: string) {
  const query = isUuid(runId)
    ? supabase.from("pipeline_runs").select("id, run_id").eq("id", runId)
    : supabase.from("pipeline_runs").select("id, run_id").eq("run_id", runId);
  const { data, error } = await query.limit(1).single();

  if (error || !data) {
    return null;
  }

  return data;
}

function errorResponse(error: unknown, fallbackMessage: string, status = 502) {
  return NextResponse.json(
    {
      error: error instanceof Error ? error.message : fallbackMessage,
    },
    { status }
  );
}

async function forwardConfigRequest(method: "GET" | "PATCH", request: Request, userId: string) {
  const body = method === "PATCH" ? await request.text() : undefined;
  const data = await orchestratorRequest(
    "/config/",
    {
      method,
      body,
    },
    userId
  );

  return NextResponse.json(data);
}

async function forwardRunsHistory(request: Request, supabase: Awaited<ReturnType<typeof createClient>>) {
  const { searchParams } = new URL(request.url);
  const limit = Number(searchParams.get("limit") || "20");
  const offset = Number(searchParams.get("offset") || "0");

  const { data, error } = await supabase
    .from("pipeline_runs")
    .select("*")
    .order("started_at", { ascending: false })
    .range(offset, offset + Math.max(limit, 1) - 1);

  if (error) {
    return errorResponse(new Error(error.message), "Failed to load run history.", 500);
  }

  return NextResponse.json(data || []);
}

async function forwardRunDetails(
  runId: string,
  supabase: Awaited<ReturnType<typeof createClient>>
) {
  const query = isUuid(runId)
    ? supabase.from("pipeline_runs").select("*").eq("id", runId)
    : supabase.from("pipeline_runs").select("*").eq("run_id", runId);
  const { data, error } = await query.limit(1).single();

  if (error || !data) {
    return NextResponse.json({ error: "Run not found." }, { status: 404 });
  }

  return NextResponse.json(data);
}

async function forwardRunMutation(
  request: Request,
  supabase: Awaited<ReturnType<typeof createClient>>,
  userId: string,
  pathSegments: string[]
) {
  if (pathSegments[0] === "trigger") {
    const payload = (await request.json().catch(() => ({}))) as Record<string, unknown>;
    const data = await orchestratorRequest(
      "/runs/trigger",
      {
        method: "POST",
        body: JSON.stringify({
          ...payload,
          user_id: userId,
        }),
      },
      userId
    );
    return NextResponse.json(data);
  }

  const [runId, action] = pathSegments;
  if (!runId || !action) {
    return NextResponse.json({ error: "Unsupported orchestrator route." }, { status: 404 });
  }

  const ownedRun = await verifyRunOwnership(supabase, runId);
  if (!ownedRun) {
    return NextResponse.json({ error: "Run not found." }, { status: 404 });
  }

  const body = action === "rerun-stage" ? await request.text() : undefined;
  const data = await orchestratorRequest(
    `/runs/${ownedRun.id}/${action}`,
    {
      method: "POST",
      body,
    },
    userId
  );

  return NextResponse.json(data);
}

async function handleRequest(method: "GET" | "POST" | "PATCH", request: Request, context: RouteContext) {
  const { path } = await context.params;
  const [resource, ...rest] = path;

  if (!resource) {
    return NextResponse.json({ error: "Unsupported orchestrator route." }, { status: 404 });
  }

  const { supabase, user } = await getAuthenticatedUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    if (resource === "config" && (method === "GET" || method === "PATCH")) {
      return await forwardConfigRequest(method, request, user.id);
    }

    if (resource === "runs" && method === "GET" && rest[0] === "history") {
      return await forwardRunsHistory(request, supabase);
    }

    if (resource === "runs" && method === "GET" && rest.length === 1) {
      return await forwardRunDetails(rest[0], supabase);
    }

    if (resource === "runs" && method === "POST") {
      return await forwardRunMutation(request, supabase, user.id, rest);
    }

    return NextResponse.json({ error: "Unsupported orchestrator route." }, { status: 404 });
  } catch (error) {
    return errorResponse(error, "Failed to contact orchestrator.");
  }
}

export async function GET(request: Request, context: RouteContext) {
  return handleRequest("GET", request, context);
}

export async function POST(request: Request, context: RouteContext) {
  return handleRequest("POST", request, context);
}

export async function PATCH(request: Request, context: RouteContext) {
  return handleRequest("PATCH", request, context);
}
