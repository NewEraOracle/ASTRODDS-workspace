import { buildStrongBuyBankrollSnapshot, type StrongBuyBankrollSnapshot, type StrongBuyExposureLabel } from "./bankroll-config";
import type { CombinedRiskGateDiagnostics, CombinedRiskGateRow } from "./combined-risk-gate";

export type BestBetStatus = "strong_buy" | "daily_pick" | "buy" | "watch" | "blocked";
export type BestBetStakeRecommendation = "5% bankroll" | "manual dashboard only" | "no stake / monitor" | "no bet";

export type BestBetRow = {
  bestBetId: string;
  rank: number;
  score: number;
  strongBuyId?: string;
  gameId?: string;
  date?: string;
  gameDate?: string;
  gameTime?: string;
  homeTeam?: string;
  awayTeam?: string;
  opponent?: string;
  gameStatusValidation?: CombinedRiskGateRow["gameStatusValidation"];
  mlbStatus?: CombinedRiskGateRow["mlbStatus"];
  gameStatusBlockReasons: string[];
  selectedSide?: string;
  marketType: "moneyline";
  marketPrice?: number | null;
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
  whyDailyPick?: string;
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
  dailyPickCount: number;
  buyCount: number;
  watchCount: number;
  blockedCount: number;
  actionableCount: number;
  visibleBoardCount: number;
  targetDailyPickMin: number;
  targetDailyPickMax: number;
  validCandidateCount: number;
  whyNoDailyPicks: string[];
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

function hasGameStatusBlock(row: CombinedRiskGateRow) {
  return Boolean(row.gameStatusValidation && !row.gameStatusValidation.isGameActiveForBetting);
}

function edgePctFromRaw(row: CombinedRiskGateRow) {
  if (typeof row.rawModelProbability !== "number" || !Number.isFinite(row.rawModelProbability)) return null;
  if (typeof row.marketProbability !== "number" || !Number.isFinite(row.marketProbability)) return null;
  return (row.rawModelProbability - row.marketProbability) * 100;
}

function sortedStatusRank(status: BestBetStatus) {
  if (status === "strong_buy") return 4;
  if (status === "daily_pick") return 3;
  if (status === "buy") return 2;
  if (status === "watch") return 1;
  return 0;
}

function clampScore(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function normalizedRiskLevel(value: CombinedRiskGateRow["riskLevel"]) {
  return (value ?? "unknown").toLowerCase();
}

function normalizedConfidence(value?: string) {
  return (value ?? "").trim().toLowerCase();
}

function candidateEdgePct(row: CombinedRiskGateRow) {
  const calibratedEdgePct = row.diagnosticCalibratedEdgePct;
  const rawEdgePct = edgePctFromRaw(row);
  return calibratedEdgePct ?? rawEdgePct;
}

function gameTimeFromDate(value?: string) {
  if (!value) return undefined;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime()) || !value.includes("T")) return undefined;
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

function gameDateFromRow(row: CombinedRiskGateRow) {
  return row.gameStatusValidation?.officialDate ?? row.date;
}

function opponentForRow(row: CombinedRiskGateRow, selectedSide?: string) {
  const side = (selectedSide ?? row.selectedSide ?? row.researchSide ?? "").trim().toLowerCase();
  const home = (row.homeTeam ?? "").trim().toLowerCase();
  const away = (row.awayTeam ?? "").trim().toLowerCase();
  if (side && side === home) return row.awayTeam ?? row.homeTeam ?? undefined;
  if (side && side === away) return row.homeTeam ?? row.awayTeam ?? undefined;
  return row.awayTeam ?? row.homeTeam ?? undefined;
}

function isDailyPickCandidate(row: CombinedRiskGateRow, status: BestBetStatus, edgePct: number | null) {
  if (status === "strong_buy" || status === "blocked") return false;
  if (row.marketType !== "moneyline") return false;
  if (!row.gameStatusValidation?.isGameActiveForBetting) return false;
  if (typeof row.marketProbability !== "number" || !Number.isFinite(row.marketProbability)) return false;
  if (!row.selectedSide) return false;

  const confidence = normalizedConfidence(row.matchConfidence);
  if (confidence !== "high" && confidence !== "medium") return false;

  const riskLevel = normalizedRiskLevel(row.riskLevel);
  if (riskLevel !== "low" && riskLevel !== "medium") return false;

  const noSevereContextRisk = !hasHighContextRisk(row);
  const noSevereDataRisk = !hasSevereDataQualityWarning(row);
  const positiveEdge = typeof edgePct === "number" ? edgePct > 0 : false;
  const relativeAdvantage = typeof row.calibratedProbability === "number" && typeof row.marketProbability === "number"
    ? row.calibratedProbability > row.marketProbability
    : typeof row.rawModelProbability === "number" && typeof row.marketProbability === "number"
      ? row.rawModelProbability > row.marketProbability
      : false;

  return noSevereContextRisk && noSevereDataRisk && (positiveEdge || relativeAdvantage);
}

function rankDailyPickScore(row: CombinedRiskGateRow, status: BestBetStatus, edgePct: number | null) {
  const confidence = normalizedConfidence(row.matchConfidence);
  const riskLevel = normalizedRiskLevel(row.riskLevel);
  const edgeBonus = typeof edgePct === "number" ? Math.max(-10, Math.min(10, edgePct)) : 0;
  const confidenceBonus = confidence === "high" ? 8 : confidence === "medium" ? 4 : 0;
  const riskBonus = riskLevel === "low" ? 6 : riskLevel === "medium" ? 2 : 0;
  const marketBonus = typeof row.marketProbability === "number" ? 6 : -12;
  const dataPenalty = hasSevereDataQualityWarning(row) ? 12 : 0;
  const contextPenalty = hasHighContextRisk(row) ? 6 : 0;
  const statusBonus = status === "strong_buy" ? 16 : status === "buy" ? 10 : status === "watch" ? 2 : 0;
  return clampScore(50 + edgeBonus + confidenceBonus + riskBonus + marketBonus + statusBonus - dataPenalty - contextPenalty - row.riskScore / 2);
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
    || hasGameStatusBlock(row)
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
    && !hasGameStatusBlock(row)
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
    : status === "daily_pick"
      ? "Daily Pick gate passed: valid MLB game, positive edge, and acceptable risk."
    : status === "buy"
      ? "Buy gate passed for dashboard tracking, but guardrails are not clean enough for Strong Buy."
      : status === "watch"
        ? "Watchlist only: edge or data support is present, but more confirmation is needed."
        : "Blocked: critical inputs or guardrails are missing.";

  return uniqueStrings([
    statusReason,
    ...(row.gameStatusValidation && !row.gameStatusValidation.isGameActiveForBetting ? row.gameStatusBlockReasons : []),
    ...row.positiveReasons,
  ]).slice(0, 6);
}

function buildMainReason(row: CombinedRiskGateRow, status: BestBetStatus, edgePct?: number | null) {
  if (status === "strong_buy") {
    return row.positiveReasons[0] ?? "Strong Buy gate passed with low risk and a verified market match.";
  }
  if (status === "daily_pick") {
    return row.positiveReasons[0] ?? "Daily Pick gate passed with valid game status, positive edge, and acceptable risk.";
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
  if (status === "daily_pick") {
    return row.downgradeReasons[0]
      ?? "Daily Pick is valid for the board, but not clean enough for Strong Buy.";
  }
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
  return row.gameStatusBlockReasons[0]
    ?? row.blockReasons[0]
    ?? row.downgradeReasons[0]
    ?? "Blocked by missing market data, high risk, or unsupported market conditions.";
}

function buildStakeRecommendation(status: BestBetStatus): BestBetStakeRecommendation {
  if (status === "strong_buy") return "5% bankroll";
  if (status === "daily_pick") return "5% bankroll";
  if (status === "buy") return "manual dashboard only";
  if (status === "watch") return "no stake / monitor";
  return "no bet";
}

function buildWarnings(row: CombinedRiskGateRow, status: BestBetStatus, bankroll: StrongBuyBankrollSnapshot) {
  return uniqueStrings([
    ...row.downgradeReasons,
    ...row.gameStatusBlockReasons,
    ...(status === "blocked" ? row.blockReasons : []),
    ...bankroll.warnings,
    status !== "strong_buy" ? "Telegram Strong Buy alerts are blocked for non-Strong Buy rows." : undefined,
    status === "daily_pick" ? "Daily Pick rows are dashboard only. Manual review required." : undefined,
    status === "buy" ? "Buy rows are dashboard only. Manual review required." : undefined,
    "Manual action only. Real-money automation remains OFF.",
  ]).slice(0, 8);
}

function buildNoDailyPickReasons(rows: CombinedRiskGateRow[]) {
  const validRows = rows.filter((row) => row.gameStatusValidation?.isGameActiveForBetting);
  const reasons = [
    validRows.length === 0 ? "No valid MLB game status rows were available." : undefined,
    validRows.every((row) => typeof row.marketProbability !== "number" || !Number.isFinite(row.marketProbability)) ? "Missing market prices." : undefined,
    validRows.every((row) => normalizedConfidence(row.matchConfidence) === "none" || normalizedConfidence(row.matchConfidence) === "low") ? "Low match confidence." : undefined,
    validRows.every((row) => normalizedRiskLevel(row.riskLevel) === "high" || normalizedRiskLevel(row.riskLevel) === "unknown") ? "All candidates are high risk." : undefined,
    validRows.every((row) => {
      const edgePct = candidateEdgePct(row);
      return typeof edgePct !== "number" || edgePct <= 0;
    }) ? "No positive edge." : undefined,
  ];

  return uniqueStrings([
    ...reasons,
    "No valid Daily Pick candidates cleared the guardrails.",
  ]);
}

type SeededBestBetRow = BestBetRow & {
  baseStatus: BestBetStatus;
  dailyPickCandidate: boolean;
  edgePct: number | null;
  selectedSide: string;
  score: number;
  gameDate?: string;
  gameTime?: string;
  opponent?: string;
  sourceRow: CombinedRiskGateRow;
};

export function buildStrongBuyGate(input: BuildBestBetsInput = {}): BestBetsResult {
  const bankroll = buildStrongBuyBankrollSnapshot({
    realizedSettledPaperPnL: input.realizedSettledPaperPnL,
    openRows: input.openLedgerRows,
  });
  const combinedRows = (input.combinedRiskRows ?? []).filter((row) => row.marketType === "moneyline");

  const seededRows = combinedRows.map<SeededBestBetRow>((row) => {
    const baseStatus = classifyBestBetStatus(row);
    const edgePct = candidateEdgePct(row);
    const selectedSide = displaySelectedSide(row) ?? row.selectedSide ?? row.researchSide ?? row.homeTeam ?? row.awayTeam ?? "Unavailable";
    const gameDate = gameDateFromRow(row);
    const gameTime = gameTimeFromDate(row.date);
    const opponent = opponentForRow(row, selectedSide);
    const score = rankDailyPickScore(row, baseStatus, edgePct);

    return {
      bestBetId: row.rowId,
      strongBuyId: baseStatus === "strong_buy" ? row.rowId : undefined,
      gameId: row.gameId,
      date: row.date,
      gameDate,
      gameTime,
      homeTeam: row.homeTeam,
      awayTeam: row.awayTeam,
      opponent,
      gameStatusValidation: row.gameStatusValidation,
      mlbStatus: row.mlbStatus,
      gameStatusBlockReasons: row.gameStatusBlockReasons ?? [],
      selectedSide,
      marketType: "moneyline",
      marketPrice: row.marketProbability,
      status: baseStatus,
      statusRank: sortedStatusRank(baseStatus),
      calibratedProbability: row.calibratedProbability,
      marketProbability: row.marketProbability,
      diagnosticRawEdgePct: edgePctFromRaw(row),
      diagnosticCalibratedEdge: row.diagnosticCalibratedEdge,
      diagnosticCalibratedEdgePct: row.diagnosticCalibratedEdgePct,
      matchConfidence: row.matchConfidence,
      riskLevel: row.riskLevel,
      riskScore: row.riskScore,
      score,
      rank: 0,
      bankroll: bankroll.currentBankroll,
      stakePercent: bankroll.stakePercent,
      stakeAmount: bankroll.stakeAmount,
      totalOpenExposurePercent: bankroll.totalOpenExposurePercent,
      exposureLabel: bankroll.exposureLabel,
      reasons: buildReasons(row, baseStatus),
      mainReason: buildMainReason(row, baseStatus, edgePct),
      whyNotStrongBuy: buildWhyNotStrongBuy(row, baseStatus, edgePct),
      whyDailyPick: undefined,
      warnings: buildWarnings(row, baseStatus, bankroll),
      blockReasons: row.blockReasons,
      downgradeReasons: row.downgradeReasons,
      telegramEligible: baseStatus === "strong_buy",
      saveEligible: baseStatus === "strong_buy" || baseStatus === "buy",
      stakeRecommendation: buildStakeRecommendation(baseStatus),
      manualOnly: true,
      paperOnly: true,
      realMoneyDisabled: true,
      baseStatus,
      dailyPickCandidate: isDailyPickCandidate(row, baseStatus, edgePct),
      edgePct,
      sourceRow: row,
    };
  });

  const dailyPickCandidates = seededRows
    .filter((row) => row.baseStatus !== "strong_buy" && row.dailyPickCandidate)
    .sort((left, right) => (
      right.score - left.score
      || (right.edgePct ?? -Infinity) - (left.edgePct ?? -Infinity)
      || left.riskScore - right.riskScore
      || sortedStatusRank(right.baseStatus) - sortedStatusRank(left.baseStatus)
      || `${left.awayTeam ?? ""}${left.homeTeam ?? ""}`.localeCompare(`${right.awayTeam ?? ""}${right.homeTeam ?? ""}`)
    ));

  const targetDailyPickMin = 2;
  const targetDailyPickMax = 6;
  const validCandidateCount = dailyPickCandidates.length;
  const selectedDailyPickCount = Math.min(targetDailyPickMax, validCandidateCount);
  const selectedDailyPickIds = new Set(dailyPickCandidates.slice(0, selectedDailyPickCount).map((row) => row.bestBetId));

  const bestBetRows = seededRows.map<BestBetRow>((row) => {
    const finalStatus: BestBetStatus = row.baseStatus === "strong_buy"
      ? "strong_buy"
      : selectedDailyPickIds.has(row.bestBetId)
        ? "daily_pick"
        : row.baseStatus;

    return {
      bestBetId: row.bestBetId,
      rank: 0,
      score: row.score,
      strongBuyId: finalStatus === "strong_buy" ? row.bestBetId : undefined,
      gameId: row.gameId,
      date: row.date,
      gameDate: row.gameDate,
      gameTime: row.gameTime,
      homeTeam: row.homeTeam,
      awayTeam: row.awayTeam,
      opponent: row.opponent,
      gameStatusValidation: row.gameStatusValidation,
      mlbStatus: row.mlbStatus,
      gameStatusBlockReasons: row.gameStatusBlockReasons,
      selectedSide: row.selectedSide,
      marketType: "moneyline",
      marketPrice: row.marketPrice,
      status: finalStatus,
      statusRank: sortedStatusRank(finalStatus),
      calibratedProbability: row.calibratedProbability,
      marketProbability: row.marketProbability,
      diagnosticRawEdgePct: row.diagnosticRawEdgePct,
      diagnosticCalibratedEdge: row.diagnosticCalibratedEdge,
      diagnosticCalibratedEdgePct: row.diagnosticCalibratedEdgePct,
      matchConfidence: row.matchConfidence,
      riskLevel: row.riskLevel,
      riskScore: row.riskScore,
      bankroll: row.bankroll,
      stakePercent: row.stakePercent,
      stakeAmount: row.stakeAmount,
      totalOpenExposurePercent: row.totalOpenExposurePercent,
      exposureLabel: row.exposureLabel,
      reasons: buildReasons(row.sourceRow, finalStatus),
      mainReason: buildMainReason(row.sourceRow, finalStatus, row.edgePct),
      whyNotStrongBuy: buildWhyNotStrongBuy(row.sourceRow, finalStatus, row.edgePct),
      whyDailyPick: finalStatus === "daily_pick"
        ? row.mainReason ?? row.reasons[0] ?? "Daily Pick gate passed with valid game status and positive edge."
        : undefined,
      warnings: buildWarnings(row.sourceRow, finalStatus, bankroll),
      blockReasons: row.blockReasons,
      downgradeReasons: row.downgradeReasons,
      telegramEligible: finalStatus === "strong_buy",
      saveEligible: finalStatus === "strong_buy" || finalStatus === "buy",
      stakeRecommendation: buildStakeRecommendation(finalStatus),
      manualOnly: true,
      paperOnly: true,
      realMoneyDisabled: true,
    };
  });

  bestBetRows.sort((left, right) => (
    sortedStatusRank(right.status) - sortedStatusRank(left.status)
    || (right.score ?? -Infinity) - (left.score ?? -Infinity)
    || (right.diagnosticCalibratedEdgePct ?? -Infinity) - (left.diagnosticCalibratedEdgePct ?? -Infinity)
    || left.riskScore - right.riskScore
    || `${left.awayTeam ?? ""}${left.homeTeam ?? ""}`.localeCompare(`${right.awayTeam ?? ""}${right.homeTeam ?? ""}`)
  ));

  const rankedBestBetRows = bestBetRows.map((row, index) => ({
    ...row,
    rank: index + 1,
  }));

  const strongBuyCount = rankedBestBetRows.filter((row) => row.status === "strong_buy").length;
  const dailyPickCount = rankedBestBetRows.filter((row) => row.status === "daily_pick").length;
  const buyCount = rankedBestBetRows.filter((row) => row.status === "buy").length;
  const watchCount = rankedBestBetRows.filter((row) => row.status === "watch").length;
  const blockedCount = rankedBestBetRows.filter((row) => row.status === "blocked").length;
  const actionableCount = strongBuyCount + dailyPickCount + buyCount;
  const visibleBoardCount = strongBuyCount + dailyPickCount + buyCount + watchCount;
  const whyNoDailyPicks = validCandidateCount === 0
    ? buildNoDailyPickReasons(combinedRows)
    : validCandidateCount < targetDailyPickMin
      ? [`Only ${validCandidateCount} valid Daily Pick candidate${validCandidateCount === 1 ? "" : "s"} cleared the guardrails.`]
      : [];
  const warnings = uniqueStrings([
    ...bankroll.warnings,
    ...(input.combinedRiskDiagnostics?.warnings ?? []),
    strongBuyCount === 0
      ? (dailyPickCount > 0
        ? "No Strong Buy today - showing best Daily Picks for manual review."
        : buyCount + watchCount > 0
          ? "No Strong Buy today - showing best Buy/Watch candidates for review."
          : "No Strong Buy rows cleared all guardrails.")
      : undefined,
    dailyPickCount === 0 ? whyNoDailyPicks[0] : undefined,
    !rankedBestBetRows.length ? "No combined risk rows were available for Best Bets evaluation." : undefined,
  ]);

  return {
    bestBetsDiagnostics: {
      available: rankedBestBetRows.length > 0,
      totalRowsEvaluated: rankedBestBetRows.length,
      strongBuyCount,
      dailyPickCount,
      buyCount,
      watchCount,
      blockedCount,
      actionableCount,
      visibleBoardCount,
      targetDailyPickMin,
      targetDailyPickMax,
      validCandidateCount,
      whyNoDailyPicks,
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
    bestBetRows: rankedBestBetRows,
  };
}
