import { NextResponse } from "next/server";

import { scanAstroddsSport } from "@/lib/astrodss/sports-data/scanner";
import type { AstroddsSportFilter } from "@/lib/astrodss/sports-data/types";

const VALID_SPORTS = new Set<AstroddsSportFilter>(["ALL", "MLB", "NFL", "NBA", "NHL", "SOCCER", "TENNIS", "MMA", "OTHER"]);

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const sportParam = (searchParams.get("sport") ?? "MLB").toUpperCase() as AstroddsSportFilter;
  const sport = VALID_SPORTS.has(sportParam) ? sportParam : "MLB";

  try {
    const result = await scanAstroddsSport(sport);

    return NextResponse.json(result, {
      headers: {
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: "ASTRODDS_SCAN_FAILED",
        message: error instanceof Error ? error.message : "Unknown scanner error",
      },
      { status: 500 },
    );
  }
}
