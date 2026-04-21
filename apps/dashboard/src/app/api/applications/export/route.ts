import { NextResponse } from "next/server";

import { buildApplicationsCsv, getApplicationsForCurrentUser } from "@/lib/server/applications";
import { createClient } from "@/lib/supabase/server";

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const applications = await getApplicationsForCurrentUser();
    const csv = buildApplicationsCsv(applications);

    return new NextResponse(csv, {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="bewerblens-applications.csv"',
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error ? error.message : "Failed to export applications.",
      },
      { status: 500 }
    );
  }
}
