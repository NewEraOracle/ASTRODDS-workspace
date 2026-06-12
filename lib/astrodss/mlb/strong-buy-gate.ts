import { buildStrongBuyBankrollSnapshot, type StrongBuyBankrollSnapshot, type StrongBuyExposureLabel } from "./bankroll-config";
import type { CombinedRiskGateDiagnostics, CombinedRiskGateRow } from "./combined-risk-gate";

export type BestBetStatus = "strong_buy" | "buy" | "watch" | "blocked";

export type BestBetRow = {
  bestBetId: string;
  strongBuyId?: string;
  gameId?: string;
  date?: string;
  homeTeam?: string;
  awayTeam?: string;
  selectedSide?: string;
  marketType: "moneyline";
  status: BestBetStatus;
  calibratedProbability?: number | null;
  marketProbability?: number | null;
  diagnosticCalibratedEdge?: number | null;
  diagnosticCalibratedEdgePct?: number | null;
  matchConfidence?: string;
  riskLevel: CombinedRiskGateRow["riskLevel"];
  riskScore: number;
  bankroll: number;
  stakePercent: number;
  stakeAmount: number;
  totalOpenExposurePercent: number;
  exposureLabel: StrongBuyExposureLabel;
  reasons: string[];
  warnings: string[];
  blockReasons: string[];
  downgradeReasons: string[];
  telegramEligible: boolean;
  manualOnly: true;
  paperOnly: true;
  realMoneyDisabled: true;
};

export type BestBetsDiagnostics = StrongBuyBankrollSnapshot & {
  available: boolean;
  totalRowsEvaluated: number;
  strongBuyCount: number;
  buyCount: number;
  watchCount: number;
  blockedCount: number;
  bankroll: number;
  generatedAt: string;
  warnings: string[];
};

export type BestBetsResult = {
  bestBetsDiagnostics: BestBetsDiagnostics;
  bestBetRows: BestBetRow[];
};

type BuildBestBetsInput = {
  combinedRiskRows?: CombinedRiskGateRow[];
  combinedRiskDiagnostics?: CombinedRiskGateDiagnostics;
  realizedSettledPaperPnL?: number | null;
  openLedgerRows?: Array<{ status?: string; stakeAmount?: number | null }>;
};

function uniqueStrings(values: Array<string | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim()))));
}

function hasCriticalRisk(row: CombinedRiskGateRow, keyword: string) {
  const normalized = keyword.toLowerCase();
  return [...row.blockReasons, ...row.downgradeReasons].some((reason) => reason.toLowerCase().includes(normalized));
}

function hasSevereDataQualityWarning(row: CombinedRiskGateRow) {
  const quality = row.dataQuality.trim().toUpperCase();
  return quality.includes("LOW") || quality.includes("MISSING") || quality.includes("DATA_ONLY");
}

function hasHighContextRisk(row: CombinedRiskGateRow) {
  return (
    hasCriticalRisk(row, "injury")
    || hasCriticalRisk(row, "lineup")
    || hasCriticalRisk(row, "bullpen")
    || hasCriticalRisk(row, "weather")
    || hasCriticalRisk(row, "ballpark")
    || hasCriticalRisk(row, "pitcher")
  );
}

function sortedStatusRank(status: BestBetStatus) {
  if (status === "strong_buy") return 4;
  if (status === "buy") return 3;
  if (status === "watch") return 2;
  return 1;
}

function classifyBestBetStatus(row: CombinedRiskGateRow) {
  const edgePct = row.diagnosticCalibratedEdgePct;
  const matchConfidence = (row.matchConfidence ?? "none").toLowerCase();
  const matchConfidenceStrong = matchConfidence === "high" || (matchConfidence === "medium" && row.riskScore <= 18 && (edgePct ?? 0) >= 8);
  const positiveEdge = typeof edgePct === "number" && edgePct > 0;
  const criticalMissing = row.marketType !== "moneyline"
    || typeof row.marketProbability !== "number"
    || typeof row.calibratedProbability !== "number"
    || typeof row.diagnosticCalibratedEdgePct !== "number"
    || matchConfidence === "none"
    || matchConfidence === "low"
    || hasSevereDataQualityWarning(row);
  const hardBlock = criticalMissing || hasHighContextRisk(row) || row.riskLevel === "high";

  if (
    row.marketType === "moneyline"
    && row.decision === "bet_candidate"
    && row.riskLevel === "low"
    && typeof row.marketProbability === "number"
    && typeof row.calibratedProbability === "number"
    && typeof edgePct === "number"
    && edgePct >= 6
    && matchConfidenceStrong
    && !hasHighContextRisk(row)
    && !hasSevereDataQualityWarning(row)
  ) {
    return "strong_buy" satisfies BestBetStatus;
  }

  if (
    !hardBlock
    && positiveEdge
    && (row.riskLevel === "low" || row.riskLevel === "medium")
    && matchConfidence !== "none"
    && matchConfidence !== "low"
  ) {
    return "buy" satisfies BestBetStatus;
  }

  if (!hardBlock && (positiveEdge || row.decision === "watchlist" || row.decision === "research_only")) {
    return "watch" satisfies BestBetStatus;
  }

  return "blocked" satisfies BestBetStatus;
}

function displaySelectedSide(row: CombinedRiskGateRow) {
  const rawSide = row.selectedSide ?? row.researchSide;
  const normalized = (rawSide ?? "").trim().toLowerCase();
  if (rawSide && !["research_only", "watchlist_only", "blocked", "wait", "monitor"].includes(normalized)) {
    return rawSide;
  }
  if ((row.calibratedProbability ?? 0) >= 0.5) return row.homeTeam ?? row.awayTeam;
  return row.awayTeam ?? row.homeTeam ?? rawSide;
}

function buildReasons(row: CombinedRiskGateRow, status: BestBetStatus) {
  const statusReason = status === "strong_buy"
    ? "Strong Buy gate passed: low risk, positive calibrated edge, and verified market match."
    : status === "buy"
      ? "Buy gate passed for dashboard tracking, but guardrails are not clean enough for Strong Buy."
      : status === "watch"
        ? "Watchlist only: edge or data support is present, but more confirmation is needed."
        : "Blocked: critical inputs or guardrails are missing.";

  return uniqueStrings([
    statusReason,
    ...row.positiveReasons,
  ]).slice(0, 6);
}

function buildWarnings(row: CombinedRiskGateRow, status: BestBetStatus, bankroll: StrongBuyBankrollSnapshot) {
  return uniqueStrings([
    ...row.downgradeReasons,
    ...(status === "blocked" ? row.blockReasons : []),
    ...bankroll.warnings,
    status !== "strong_buy" ? "Telegram Strong Buy alerts are blocked for non-Strong Buy rows." : undefined,
    "Manual action only. Real-money automation remains OFF.",
  ]).slice(0, 8);
}

export function buildStrongBuyGate(input: BuildBestBetsInput = {}): BestBetsResult {
  const bankroll = buildStrongBuyBankrollSnapshot({
    realizedSettledPaperPnL: input.realizedSettledPaperPnL,
    openRows: input.openLedgerRows,
  });
  const combinedRows = (input.combinedRiskRows ?? []).filter((row) => row.marketType === "moneyline");
  const bestBetRows = combinedRows.map<BestBetRow>((row) => {
    const status = classifyBestBetStatus(row);
    const selectedSide = displaySelectedSide(row);
    return {
      bestBetId: row.rowId,
      strongBuyId: status === "strong_buy" ? row.rowId : undefined,
      gameId: row.gameId,
      date: row.date,
      homeTeam: row.homeTeam,
      awayTeam: row.awayTeam,
      selectedSide,
      marketType: "moneyline",
      status,
      calibratedProbability: row.calibratedProbability,
      marketProbability: row.marketProbability,
      diagnosticCalibratedEdge: row.diagnosticCalibratedEdge,
      diagnosticCalibratedEdgePct: row.diagnosticCalibratedEdgePct,
      matchConfidence: row.matchConfidence,
      riskLevel: row.riskLevel,
      riskScore: row.riskScore,
      bankroll: bankroll.currentBankroll,
      stakePercent: bankroll.stakePercent,
      stakeAmount: bankroll.stakeAmount,
      totalOpenExposurePercent: bankroll.totalOpenExposurePercent,
      exposureLabel: bankroll.exposureLabel,
      reasons: buildReasons(row, status),
      warnings: buildWarnings(row, status, bankroll),
      blockReasons: row.blockReasons,
      downgradeReasons: row.downgradeReasons,
      telegramEligible: status === "strong_buy",
      manualOnly: true,
      paperOnly: true,
      realMoneyDisabled: true,
    };
  });

  bestBetRows.sort((left, right) => (
    sortedStatusRank(right.status) - sortedStatusRank(left.status)
    || (right.diagnosticCalibratedEdgePct ?? -Infinity) - (left.diagnosticCalibratedEdgePct ?? -Infinity)
    || left.riskScore - right.riskScore
    || `${left.awayTeam ?? ""}${left.homeTeam ?? ""}`.localeCompare(`${right.awayTeam ?? ""}${right.homeTeam ?? ""}`)
  ));

  const strongBuyCount = bestBetRows.filter((row) => row.status === "strong_buy").length;
  const buyCount = bestBetRows.filter((row) => row.status === "buy").length;
  const watchCount = bestBetRows.filter((row) => row.status === "watch").length;
  const blockedCount = bestBetRows.filter((row) => row.status === "blocked").length;
  const warnings = uniqueStrings([
    ...bankroll.warnings,
    ...(input.combinedRiskDiagnostics?.warnings ?? []),
    strongBuyCount === 0 ? "No Strong Buy rows cleared all guardrails." : undefined,
    !bestBetRows.length ? "No combined risk rows were available for Best Bets evaluation." : undefined,
  ]);

  return {
    bestBetsDiagnostics: {
      available: bestBetRows.length > 0,
      totalRowsEvaluated: bestBetRows.length,
      strongBuyCount,
      buyCount,
      watchCount,
      blockedCount,
      bankroll: bankroll.currentBankroll,
      stakePercent: bankroll.stakePercent,
      stakeAmount: bankroll.stakeAmount,
      totalOpenStakeAmount: bankroll.totalOpenStakeAmount,
      totalOpenExposurePercent: bankroll.totalOpenExposurePercent,
      remainingUnexposedBankroll: bankroll.remainingUnexposedBankroll,
      exposureLabel: bankroll.exposureLabel,
      openStrongBuyCount: bankroll.openStrongBuyCount,
      currentBankroll: bankroll.currentBankroll,
      startingBankroll: bankroll.startingBankroll,
      generatedAt: new Date().toISOString(),
      warnings,
    },
    bestBetRows,
  };
}
