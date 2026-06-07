import { NextResponse } from "next/server";

import { fetchConfiguredSportsOdds, getOddsLayerStatus } from "@/lib/astrodss/sports-data/odds";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const sportKey = url.searchParams.get("sportKey") ?? "baseball_mlb";
  const fetchOdds = url.searchParams.get("fetch") === "true";
  const payload = fetchOdds ? await fetchConfiguredSportsOdds(sportKey) : { ...getOddsLayerStatus(), odds: [] };
  return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
}