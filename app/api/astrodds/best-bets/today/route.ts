import { NextResponse } from "next/server";
import { GET as getUnifiedSignals } from "@/app/api/astrodds/signals/unified/route";
import { loadStrongBuyLedgerStatus } from "@/lib/astrodss/mlb/strong-buy-ledger";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type BestBetRowResponse = {
  status: "strong_buy" | "daily_pick" | "buy" | "watch" | "blocked";
  gameStatusValidation?: {
    available: boolean;
    mlbStatus: string;
    isGameActiveForBetting: boolean;
    isPostponed: boolean;
    isSuspended: boolean;
    isCancelled: boolean;
    isFinal: boolean;
    isLive: boolean;
    isDateMismatch: boolean;
    gameStatusBlockReasons: string[];
    warnings: string[];
  };
  mlbStatus?: string;
  gameStatusBlockReasons?: string[];
};

type UnifiedBestBetsPayload = {
  bestBetsDiagnostics?: Record<string, unknown>;
  bestBetRows?: BestBetRowResponse[];
  strongBuyLedgerDiagnostics?: Record<string, unknown>;
  gameStatusValidationDiagnostics?: Record<string, unknown>;
  errors?: string[];
};

type FetchBestBetsResult = {
  status: BestBetsTodayResponse["status"];
  warnings: string[];
  payload: UnifiedBestBetsPayload | null;
};

type BestBetsTodayResponse = {
  status: "available" | "partial" | "timeout";
  ok: boolean;
  realMoneyTrading: "OFF";
  manualOnly: true;
  paperOnly: true;
  bestBetsDiagnostics: {
    available: boolean;
    totalRowsEvaluated: number;
    strongBuyCount: number;
    dailyPickCount: number;
    buyCount: number;
    watchCount: number;
    blockedCount: number;
    actionableCount: number;
    visibleBoardCount: number;
    targetDailyPickMin?: number;
    targetDailyPickMax?: number;
    validCandidateCount?: number;
    whyNoDailyPicks?: string[];
    bankroll?: number;
    stakePercent?: number;
    stakeAmount?: number;
    totalOpenStakeAmount?: number;
    totalOpenExposurePercent?: number;
    remainingUnexposedBankroll?: number;
    exposureLabel?: string;
    warnings: string[];
    generatedAt?: string;
  };
  bestBetRows: BestBetRowResponse[];
  strongBuyRows: BestBetRowResponse[];
  strongBuyLedgerDiagnostics: Record<string, unknown> | null;
  gameStatusValidationDiagnostics: Record<string, unknown> | null;
  warnings: string[];
};

function statusRank(status: BestBetRowResponse["status"]) {
  if (status === "strong_buy") return 4;
  if (status === "daily_pick") return 3;
  if (status === "buy") return 2;
  if (status === "watch") return 1;
  return 0;
}

function buildFallbackResponse(
  status: BestBetsTodayResponse["status"],
  warnings: string[],
  strongBuyLedgerDiagnostics: Record<string, unknown> | null,
  gameStatusValidationDiagnostics: Record<string, unknown> | null,
): BestBetsTodayResponse {
  return {
    status,
    ok: true,
    realMoneyTrading: "OFF",
    manualOnly: true,
    paperOnly: true,
    bestBetsDiagnostics: {
      available: true,
      totalRowsEvaluated: 0,
      strongBuyCount: 0,
      dailyPickCount: 0,
      buyCount: 0,
      watchCount: 0,
      blockedCount: 0,
      actionableCount: 0,
      visibleBoardCount: 0,
      targetDailyPickMin: 2,
      targetDailyPickMax: 6,
      validCandidateCount: 0,
      whyNoDailyPicks: warnings,
      warnings,
      generatedAt: new Date().toISOString(),
    },
    bestBetRows: [],
    strongBuyRows: [],
    strongBuyLedgerDiagnostics,
    gameStatusValidationDiagnostics,
    warnings,
  };
}

async function fetchUnifiedBestBets(request: Request): Promise<FetchBestBetsResult> {
  const unifiedUrl = new URL("/api/astrodds/signals/unified?sport=MLB", request.url);
  const timeoutMs = 15_000;
  const unifiedRequest = new Request(unifiedUrl, {
    method: "GET",
    headers: {
      "x-astrodds-best-bets": "today",
    },
  });

  let timeoutHandle: ReturnType<typeof setTimeout> | undefined;
  const timeoutPromise = new Promise<FetchBestBetsResult>((resolve) => {
    timeoutHandle = setTimeout(() => {
      resolve({
        status: "timeout",
        warnings: [`Best Bets unified request timed out after ${timeoutMs / 1000} seconds.`],
        payload: null,
      });
    }, timeoutMs);
  });

  try {
    const unifiedPromise = (async () => {
      try {
        const response = await getUnifiedSignals(unifiedRequest);

        if (!response.ok) {
          return {
            status: "partial" as const,
            warnings: [`Unified MLB route failed with ${response.status}.`],
            payload: null,
          };
        }

        const text = await response.text();
        if (!text.trim()) {
          return {
            status: "partial" as const,
            warnings: ["Unified MLB route returned an empty body."],
            payload: null,
          };
        }

        const payload = JSON.parse(text) as UnifiedBestBetsPayload;
        return {
          status: "available" as const,
          warnings: payload.errors ?? [],
          payload,
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown Best Bets fetch failure.";
        return {
          status: "partial" as const,
          warnings: [`Best Bets unified request failed: ${message}`],
          payload: null,
        };
      }
    })();

    return await Promise.race([unifiedPromise, timeoutPromise]);
  } finally {
    if (timeoutHandle) clearTimeout(timeoutHandle);
  }
}

export async function GET(request: Request) {
  const [ledgerDiagnostics, unified] = await Promise.all([
    loadStrongBuyLedgerStatus().catch(() => null),
    fetchUnifiedBestBets(request),
  ]);
  const rows = [...(unified.payload?.bestBetRows ?? [])].sort((left, right) => statusRank(right.status) - statusRank(left.status));
  const warnings = [
    ...(unified.warnings ?? []),
    ...(unified.payload?.errors ?? []),
  ];

  const fallback = !unified.payload
    ? buildFallbackResponse(unified.status, warnings.length ? warnings : ["Best Bets diagnostics unavailable."], ledgerDiagnostics, null)
    : null;

  const responseBody: BestBetsTodayResponse = fallback ?? {
    status: unified.status,
    ok: true,
    realMoneyTrading: "OFF",
    manualOnly: true,
    paperOnly: true,
    bestBetsDiagnostics: {
      available: true,
      totalRowsEvaluated: rows.length,
      strongBuyCount: rows.filter((row) => row.status === "strong_buy").length,
      dailyPickCount: rows.filter((row) => row.status === "daily_pick").length,
      buyCount: rows.filter((row) => row.status === "buy").length,
      watchCount: rows.filter((row) => row.status === "watch").length,
      blockedCount: rows.filter((row) => row.status === "blocked").length,
      actionableCount: rows.filter((row) => row.status === "strong_buy" || row.status === "daily_pick" || row.status === "buy").length,
      visibleBoardCount: rows.filter((row) => row.status !== "blocked").length,
      targetDailyPickMin: typeof unified.payload?.bestBetsDiagnostics?.targetDailyPickMin === "number" ? unified.payload.bestBetsDiagnostics.targetDailyPickMin : 2,
      targetDailyPickMax: typeof unified.payload?.bestBetsDiagnostics?.targetDailyPickMax === "number" ? unified.payload.bestBetsDiagnostics.targetDailyPickMax : 6,
      validCandidateCount: typeof unified.payload?.bestBetsDiagnostics?.validCandidateCount === "number" ? unified.payload.bestBetsDiagnostics.validCandidateCount : rows.filter((row) => row.status === "daily_pick" || row.status === "buy" || row.status === "watch" || row.status === "strong_buy").length,
      whyNoDailyPicks: Array.isArray(unified.payload?.bestBetsDiagnostics?.whyNoDailyPicks) ? (unified.payload.bestBetsDiagnostics.whyNoDailyPicks as string[]) : (rows.some((row) => row.status === "daily_pick") ? [] : warnings),
      bankroll: typeof unified.payload?.bestBetsDiagnostics?.bankroll === "number" ? unified.payload.bestBetsDiagnostics.bankroll : ledgerDiagnostics?.currentBankroll,
      stakePercent: typeof unified.payload?.bestBetsDiagnostics?.stakePercent === "number" ? unified.payload.bestBetsDiagnostics.stakePercent : 5,
      stakeAmount: typeof unified.payload?.bestBetsDiagnostics?.stakeAmount === "number" ? unified.payload.bestBetsDiagnostics.stakeAmount : 50,
      totalOpenStakeAmount: typeof unified.payload?.bestBetsDiagnostics?.totalOpenStakeAmount === "number" ? unified.payload.bestBetsDiagnostics.totalOpenStakeAmount : ledgerDiagnostics?.totalOpenStakeAmount,
      totalOpenExposurePercent: typeof unified.payload?.bestBetsDiagnostics?.totalOpenExposurePercent === "number" ? unified.payload.bestBetsDiagnostics.totalOpenExposurePercent : ledgerDiagnostics?.totalOpenExposurePercent,
      remainingUnexposedBankroll: typeof unified.payload?.bestBetsDiagnostics?.remainingUnexposedBankroll === "number" ? unified.payload.bestBetsDiagnostics.remainingUnexposedBankroll : ledgerDiagnostics?.remainingUnexposedBankroll,
      exposureLabel: typeof unified.payload?.bestBetsDiagnostics?.exposureLabel === "string" ? unified.payload.bestBetsDiagnostics.exposureLabel : ledgerDiagnostics?.exposureLabel,
      warnings: warnings.length ? warnings : ["Best Bets diagnostics loaded successfully."],
      generatedAt: typeof unified.payload?.bestBetsDiagnostics?.generatedAt === "string" ? unified.payload.bestBetsDiagnostics.generatedAt : new Date().toISOString(),
    },
    bestBetRows: rows,
    strongBuyRows: rows.filter((row) => row.status === "strong_buy"),
    strongBuyLedgerDiagnostics: unified.payload?.strongBuyLedgerDiagnostics ?? ledgerDiagnostics,
    gameStatusValidationDiagnostics: unified.payload?.gameStatusValidationDiagnostics ?? null,
    warnings: warnings.length ? warnings : [],
  };

  return NextResponse.json(responseBody, {
    status: 200,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}
