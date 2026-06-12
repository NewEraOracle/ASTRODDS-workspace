import { buildStrongBuyBankrollSnapshot, type StrongBuyBankrollSnapshot, type StrongBuyExposureLabel } from "./bankroll-config";
import type { CombinedRiskGateDiagnostics, CombinedRiskGateRow } from "./combined-risk-gate";

export type BestBetStatus = "strong_buy" | "buy" | "watch" | "blocked";
export type BestBetStakeRecommendation = "5% bankroll" | "manual dashboard only" | "no stake / monitor" | "no bet";

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
  statusRank: number;
  calibratedProbability?: number | null;
  marketProbability?: number | null;
  diagnosticRawEdgePct?: number | null;
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
  mainReason: string;
  whyNotStrongBuy?: string;
  warnings: string[];
  blockReasons: string[];
  downgradeReasons: string[];
  telegramEligible: boolean;
  saveEligible: boolean;
  stakeRecommendation: BestBetStakeRecommendation;
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
  actionableCount: number;
  visibleBoardCount: number;
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

function edgePctFromRaw(row: CombinedRiskGateRow) {
  if (typeof row.rawModelProbability !== "number" || !Number.isFinite(row.rawModelProbability)) return null;
  if (typeof row.marketProbability !== "number" || !Number.isFinite(row.marketProbability)) return null;
  return (row.rawModelProbability - row.marketProbability) * 100;
}

function sortedStatusRank(status: BestBetStatus) {
  if (status === "strong_buy") return 4;
  if (status === "buy") return 3;
  if (status === "watch") return 2;
  return 1;
}

function classifyBestBetStatus(row: CombinedRiskGateRow) {
  const calibratedEdgePct = row.diagnosticCalibratedEdgePct;
  const rawEdgePct = edgePctFromRaw(row);
  const edgePct = calibratedEdgePct ?? rawEdgePct;
  const matchConfidence = (row.matchConfidence ?? "none").toLowerCase();
  const matchConfidenceStrong = matchConfidence === "high" || (matchConfidence === "medium" && row.riskScore <= 18 && (edgePct ?? 0) >= 8);
  const marketReady = typeof row.marketProbability === "number" && Number.isFinite(row.marketProbability);
  const hasAnyModelSignal = typeof row.calibratedProbability === "number" || typeof row.rawModelProbability === "number";
  const hardBlock = row.marketType !== "moneyline"
    || !marketReady
    || matchConfidence === "none"
    || matchConfidence === "low"
    || hasSevereDataQualityWarning(row)
    || hasHighContextRisk(row)
    || row.riskLevel === "high"
    || (!hasAnyModelSignal && row.decision !== "research_only");

  if (
    row.marketType === "moneyline"
    && row.decision === "bet_candidate"
    && row.riskLevel === "low"
    && typeof row.marketProbability === "number"
    && typeof row.calibratedProbability === "number"
    && typeof calibratedEdgePct === "number"
    && calibratedEdgePct >= 6
    && matchConfidenceStrong
    && !hasHighContextRisk(row)
    && !hasSevereDataQualityWarning(row)
  ) {
    return "strong_buy" satisfies BestBetStatus;
  }

  if (typeof edgePct === "number" && edgePct <= 0) {
    return "blocked" satisfies BestBetStatus;
  }

  if (
    !hardBlock
    && marketReady
    && hasAnyModelSignal
    && (row.riskLevel === "low" || row.riskLevel === "medium")
    && matchConfidence !== "none"
    && matchConfidence !== "low"
  ) {
    if (typeof edgePct === "number" && edgePct >= 3 && !hasHighContextRisk(row)) {
      return "buy" satisfies BestBetStatus;
    }
  }

  if (
    !hardBlock
    && marketReady
    && hasAnyModelSignal
    && (row.decision === "watchlist" || row.decision === "research_only" || typeof edgePct !== "number" || (typeof edgePct === "number" && edgePct > 0))
  ) {
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

function buildMainReason(row: CombinedRiskGateRow, status: BestBetStatus, edgePct?: number | null) {
  if (status === "strong_buy") {
    return row.positiveReasons[0] ?? "Strong Buy gate passed with low risk and a verified market match.";
  }
  if (status === "buy") {
    return row.positiveReasons[0] ?? "Positive model signal and usable market data, but the setup is not clean enough for Strong Buy.";
  }
  if (status === "watch") {
    return row.positiveReasons[0] ?? "Useful model signal with partial confirmation, but edge or data quality is still incomplete.";
  }
  return row.blockReasons[0]
    ?? row.downgradeReasons[0]
    ?? (typeof edgePct === "number" && edgePct < 0
      ? "Negative edge with no compensating signal."
      : "Critical inputs or guardrails are missing.");
}

function buildWhyNotStrongBuy(row: CombinedRiskGateRow, status: BestBetStatus, edgePct?: number | null) {
  if (status === "strong_buy") return undefined;
  if (status === "buy") {
    return row.downgradeReasons[0]
      ?? "Strong Buy failed only because edge/risk guardrails are not fully clean yet.";
  }
  if (status === "watch") {
    return row.downgradeReasons[0]
      ?? (typeof edgePct === "number" && edgePct > 0
        ? "Edge is positive, but the setup is still partial."
        : "Edge is weak or missing, so this remains on watch.");
  }
  return row.blockReasons[0]
    ?? row.downgradeReasons[0]
    ?? "Blocked by missing market data, high risk, or unsupported market conditions.";
}

function buildStakeRecommendation(status: BestBetStatus): BestBetStakeRecommendation {
  if (status === "strong_buy") return "5% bankroll";
  if (status === "buy") return "manual dashboard only";
  if (status === "watch") return "no stake / monitor";
  return "no bet";
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
    const calibratedEdgePct = row.diagnosticCalibratedEdgePct;
    const rawEdgePct = edgePctFromRaw(row);
    const edgePct = calibratedEdgePct ?? rawEdgePct;
    const selectedSide = displaySelectedSide(row);
    const statusRank = sortedStatusRank(status);
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
      statusRank,
      calibratedProbability: row.calibratedProbability,
      marketProbability: row.marketProbability,
      diagnosticRawEdgePct: rawEdgePct,
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
      mainReason: buildMainReason(row, status, edgePct),
      whyNotStrongBuy: buildWhyNotStrongBuy(row, status, edgePct),
      warnings: buildWarnings(row, status, bankroll),
      blockReasons: row.blockReasons,
      downgradeReasons: row.downgradeReasons,
      telegramEligible: status === "strong_buy",
      saveEligible: status === "strong_buy" || status === "buy",
      stakeRecommendation: buildStakeRecommendation(status),
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
  const actionableCount = strongBuyCount + buyCount;
  const visibleBoardCount = strongBuyCount + buyCount + watchCount;
  const warnings = uniqueStrings([
    ...bankroll.warnings,
    ...(input.combinedRiskDiagnostics?.warnings ?? []),
    strongBuyCount === 0
      ? (buyCount + watchCount > 0
        ? "No Strong Buy today — showing best Buy/Watch candidates for review."
        : "No Strong Buy rows cleared all guardrails.")
      : undefined,
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
      actionableCount,
      visibleBoardCount,
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
