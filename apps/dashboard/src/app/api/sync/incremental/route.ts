import { NextResponse } from "next/server";

import { triggerPipelineRun } from "@/lib/server/orchestrator";
import { createClient } from "@/lib/supabase/server";

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data: profile, error: profileError } = await supabase
    .from("user_profiles")
    .select("gmail_connected_at")
    .eq("id", user.id)
    .single();

  if (profileError) {
    return NextResponse.json({ error: profileError.message }, { status: 500 });
  }

  if (!profile?.gmail_connected_at) {
    return NextResponse.json({ error: "Connect Gmail before starting incremental sync." }, { status: 400 });
  }

  const { error: updateError } = await supabase
    .from("user_profiles")
    .update({
      sync_mode: "incremental",
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
      triggeredBy: "incremental",
    });

    return NextResponse.json({
      message: "Incremental sync queued.",
      run,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to queue incremental sync.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
