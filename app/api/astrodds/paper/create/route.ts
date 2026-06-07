import { NextResponse } from "next/server";

import { addOfficialPaperPick, addModelLeanRecord } from "@/lib/astrodss/paper/paper-ledger";

export const dynamic = "force-dynamic";

type CreatePaperRequest = {
  kind?: "official" | "model_lean";
  payload?: Record<string, unknown>;
};

function text(value: unknown, fallback = "UNKNOWN") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function numberValue(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as CreatePaperRequest;
  const payload = body.payload ?? {};

  if (body.kind === "model_lean") {
    const record = await addModelLeanRecord({
      sport: text(payload.sport, "MLB"),
      league: typeof payload.league === "string" ? payload.league : undefined,
      gameId: typeof payload.gameId === "string" ? payload.gameId : undefined,
      game: text(payload.game),
      leanSide: text(payload.leanSide, "WAIT"),
      confidence: numberValue(payload.confidence),
      modelScore: numberValue(payload.modelScore),
      dataQuality: text(payload.dataQuality, "UNKNOWN"),
      reason: text(payload.reason, "Model lean saved for validation."),
      missingDataWarnings: Array.isArray(payload.missingDataWarnings) ? payload.missingDataWarnings.filter((item): item is string => typeof item === "string") : [],
      source: text(payload.source, "ASTRODDS_MODEL_LEAN"),
    });

    return NextResponse.json({ ok: true, realMoneyTrading: "OFF", record });
  }

  const paperStakePercent = numberValue(payload.paperStakePercent);
  const paperStakeUnits = numberValue(payload.paperStakeUnits);
  const decisionLabel = text(payload.decisionLabel, "BUY");
  if (!["BUY", "STRONG BUY", "ELITE"].includes(decisionLabel)) {
    return NextResponse.json({ ok: false, error: "Official paper pick requires BUY, STRONG BUY, or ELITE." }, { status: 400 });
  }
  if (paperStakePercent <= 0 || paperStakeUnits <= 0) {
    return NextResponse.json({ ok: false, error: "Official paper pick requires paper stake greater than 0." }, { status: 400 });
  }
  if (
    typeof payload.entryPriceAmerican !== "number" &&
    typeof payload.entryPriceDecimal !== "number" &&
    typeof payload.entryPricePolymarket !== "number"
  ) {
    return NextResponse.json({ ok: false, error: "Official paper pick requires real odds or market entry price." }, { status: 400 });
  }

  const pick = await addOfficialPaperPick({
    category: text(payload.category, "sports") === "polymarket" ? "polymarket" : "sports",
    sport: typeof payload.sport === "string" ? payload.sport : undefined,
    league: typeof payload.league === "string" ? payload.league : undefined,
    gameId: typeof payload.gameId === "string" ? payload.gameId : undefined,
    game: text(payload.game),
    marketType: text(payload.marketType),
    marketLabel: text(payload.marketLabel),
    pickSide: text(payload.pickSide),
    entryPriceAmerican: typeof payload.entryPriceAmerican === "number" ? payload.entryPriceAmerican : undefined,
    entryPriceDecimal: typeof payload.entryPriceDecimal === "number" ? payload.entryPriceDecimal : undefined,
    entryPricePolymarket: typeof payload.entryPricePolymarket === "number" ? payload.entryPricePolymarket : undefined,
    impliedProbability: typeof payload.impliedProbability === "number" ? payload.impliedProbability : undefined,
    paperStakePercent,
    paperStakeUnits,
    modelScore: numberValue(payload.modelScore),
    confidence: numberValue(payload.confidence),
    dataQuality: text(payload.dataQuality),
    decisionLabel: decisionLabel as "BUY" | "STRONG BUY" | "ELITE",
    whaleSupportLevel: ["NONE", "LOW", "MEDIUM", "HIGH"].includes(text(payload.whaleSupportLevel, "NONE"))
      ? text(payload.whaleSupportLevel, "NONE") as "NONE" | "LOW" | "MEDIUM" | "HIGH"
      : "NONE",
    whaleConflict: Boolean(payload.whaleConflict),
    reason: text(payload.reason),
    source: text(payload.source, "ASTRODDS_OFFICIAL_PAPER_PICK"),
  });

  return NextResponse.json({ ok: true, realMoneyTrading: "OFF", pick });
}