import { NextResponse } from "next/server";

import { captureDailyMlbResearchSnapshot } from "@/lib/astrodss/mlb/daily-data-capture";

export async function POST() {
  const result = await captureDailyMlbResearchSnapshot();

  return NextResponse.json(
    {
      ...result,
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
