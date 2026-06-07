import { NextResponse } from "next/server";

import { buildBacktestReport } from "@/lib/astrodss/performance";

export const dynamic = "force-dynamic";

export async function GET() {
  const report = await buildBacktestReport();

  return NextResponse.json(report, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
