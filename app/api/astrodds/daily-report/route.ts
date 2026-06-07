import { NextResponse } from "next/server";

import { buildDailyReport } from "@/lib/astrodss/performance";

export const dynamic = "force-dynamic";

export async function GET() {
  const report = await buildDailyReport();

  return NextResponse.json(report, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
