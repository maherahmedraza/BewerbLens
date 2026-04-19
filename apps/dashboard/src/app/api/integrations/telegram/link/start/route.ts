import crypto from "node:crypto";
import { addHours } from "date-fns";
import { NextResponse } from "next/server";

import { createClient } from "@/lib/supabase/server";

function generateLinkCode() {
  return crypto.randomBytes(6).toString("base64url").toUpperCase();
}

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const expiresAt = addHours(new Date(), 1).toISOString();
  const linkCode = generateLinkCode();

  await supabase
    .from("telegram_link_requests")
    .update({ status: "expired" })
    .eq("user_id", user.id)
    .eq("status", "pending");

  const { error } = await supabase.from("telegram_link_requests").insert({
    user_id: user.id,
    link_code: linkCode,
    expires_at: expiresAt,
  });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const botUsername = process.env.TELEGRAM_BOT_USERNAME || null;
  const botUrl = botUsername ? `https://t.me/${botUsername}?start=${linkCode}` : null;

  return NextResponse.json({
    link_code: linkCode,
    expires_at: expiresAt,
    bot_username: botUsername,
    bot_url: botUrl,
  });
}
