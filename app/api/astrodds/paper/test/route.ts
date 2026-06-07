import { NextResponse } from "next/server";

import { getPaperTestState, startPaperTest } from "@/lib/astrodss/paper/paper-ledger";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(await getPaperTestState(), { headers: { "Cache-Control": "no-store" } });
}

export async function POST() {
  return NextResponse.json(await startPaperTest(), { headers: { "Cache-Control": "no-store" } });
}