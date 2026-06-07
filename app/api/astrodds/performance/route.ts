import { NextResponse } from "next/server";

import { buildPerformanceReport } from "@/lib/astrodss/performance";

export const dynamic = "force-dynamic";

export async function GET() {
  const report = await buildPerformanceReport();

  return NextResponse.json(report, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
