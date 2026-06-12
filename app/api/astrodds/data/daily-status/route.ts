import { NextResponse } from "next/server";

import { loadDailyMlbResearchCaptureStatus } from "@/lib/astrodss/mlb/daily-data-capture";

export async function GET() {
  const status = await loadDailyMlbResearchCaptureStatus();

  return NextResponse.json(
    {
      ...status,
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
