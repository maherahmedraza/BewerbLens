import { NextResponse } from "next/server";

import { createAdminClient } from "@/lib/supabase/admin";

interface TelegramLinkPayload {
  code?: string;
  chatId?: string;
}

export async function POST(request: Request) {
  const expectedSecret = process.env.TELEGRAM_LINK_SECRET;
  if (expectedSecret && request.headers.get("x-telegram-link-secret") !== expectedSecret) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = (await request.json()) as TelegramLinkPayload;
  if (!payload.code || !payload.chatId) {
    return NextResponse.json({ error: "Both code and chatId are required." }, { status: 400 });
  }

  const supabase = createAdminClient();
  const now = new Date().toISOString();
  const { data: linkRequest, error: lookupError } = await supabase
    .from("telegram_link_requests")
    .select("id, user_id, expires_at")
    .eq("link_code", payload.code.toUpperCase())
    .eq("status", "pending")
    .single();

  if (lookupError || !linkRequest) {
    return NextResponse.json({ error: "Link code is invalid or already used." }, { status: 404 });
  }

  if (new Date(linkRequest.expires_at) <= new Date()) {
    await supabase
      .from("telegram_link_requests")
      .update({ status: "expired" })
      .eq("id", linkRequest.id);
    return NextResponse.json({ error: "Link code has expired." }, { status: 410 });
  }

  const { error: profileError } = await supabase
    .from("user_profiles")
    .update({
      telegram_chat_id: payload.chatId,
      telegram_enabled: true,
      telegram_connected_at: now,
    })
    .eq("id", linkRequest.user_id);

  if (profileError) {
    return NextResponse.json({ error: profileError.message }, { status: 500 });
  }

  const { error: completeError } = await supabase
    .from("telegram_link_requests")
    .update({
      status: "completed",
      telegram_chat_id: payload.chatId,
      completed_at: now,
    })
    .eq("id", linkRequest.id);

  if (completeError) {
    return NextResponse.json({ error: completeError.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
