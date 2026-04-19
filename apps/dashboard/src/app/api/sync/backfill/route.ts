import { NextResponse } from "next/server";

import { triggerPipelineRun } from "@/lib/server/orchestrator";
import { createClient } from "@/lib/supabase/server";

function isValidDate(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value);
}

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = (await request.json()) as { startDate?: string };
  const startDate = payload.startDate;

  if (!startDate || !isValidDate(startDate)) {
    return NextResponse.json({ error: "A valid backfill start date is required." }, { status: 400 });
  }

  const { error: updateError } = await supabase
    .from("user_profiles")
    .update({
      backfill_start_date: startDate,
      sync_mode: "backfill",
      sync_status: "pending",
      sync_error: null,
    })
    .eq("id", user.id);

  if (updateError) {
    return NextResponse.json({ error: updateError.message }, { status: 500 });
  }

  try {
    const run = await triggerPipelineRun({
      userId: user.id,
      triggeredBy: "backfill",
      sinceDate: startDate,
    });

    return NextResponse.json({
      message: "Backfill sync queued.",
      run,
      backfill_start_date: startDate,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to queue backfill sync.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
