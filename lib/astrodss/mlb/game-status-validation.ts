export type MLBGameStatus = "PRE_GAME" | "LIVE" | "FINAL" | "POSTPONED" | "SUSPENDED" | "CANCELLED" | "UNKNOWN";

export type MLBGameStatusSnapshot = {
  abstractGameState?: string;
  detailedState?: string;
  codedGameState?: string;
  officialDate?: string;
  normalized?: MLBGameStatus;
};

export type MLBGameStatusValidationInput = {
  gameId?: string;
  game?: string;
  startTime?: string;
  marketDate?: string;
  marketTitle?: string;
  marketPick?: string;
  liveStatus?: string;
  mlbStatus?: MLBGameStatusSnapshot;
};

export type MLBGameStatusValidation = {
  available: boolean;
  gameId?: string;
  game?: string;
  mlbStatus: MLBGameStatus;
  abstractGameState?: string;
  detailedState?: string;
  officialDate?: string;
  marketDate?: string;
  dateMatches?: boolean;
  isGameActiveForBetting: boolean;
  isPostponed: boolean;
  isSuspended: boolean;
  isCancelled: boolean;
  isFinal: boolean;
  isLive: boolean;
  isDateMismatch: boolean;
  gameStatusBlockReasons: string[];
  warnings: string[];
  source: string;
};

export type MLBGameStatusValidationDiagnostics = {
  available: boolean;
  status: "available" | "partial" | "missing";
  totalGamesEvaluated: number;
  activeGames: number;
  blockedGames: number;
  postponedGames: number;
  suspendedGames: number;
  cancelledGames: number;
  finalGames: number;
  liveGames: number;
  dateMismatchGames: number;
  missingMarketDateGames: number;
  gameStatusBlockReasons: Array<{ reason: string; count: number }>;
  warnings: string[];
  generatedAt: string;
  source: string;
  officialPickEligible: false;
  officialEdgeAllowed: false;
  isPaperOnly: true;
  realMoneyDisabled: true;
};

function uniqueStrings(values: Array<string | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim()))));
}

function dateOnly(value?: string) {
  if (!value) return undefined;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return undefined;
  return parsed.toISOString().slice(0, 10);
}

function normalizedStatus(value?: string, fallback?: string) {
  const combined = `${value ?? ""} ${fallback ?? ""}`.trim().toLowerCase();
  if (!combined) return "UNKNOWN" as const;
  if (combined.includes("postpon")) return "POSTPONED" as const;
  if (combined.includes("suspend")) return "SUSPENDED" as const;
  if (combined.includes("cancel")) return "CANCELLED" as const;
  if (combined.includes("final")) return "FINAL" as const;
  if (combined.includes("preview") || combined.includes("scheduled") || combined.includes("pre-game")) return "PRE_GAME" as const;
  if (combined.includes("live") || combined.includes("in progress")) return "LIVE" as const;
  return "UNKNOWN" as const;
}

function addReason(reasons: Map<string, number>, reason: string, count = 1) {
  if (count <= 0) return;
  reasons.set(reason, (reasons.get(reason) ?? 0) + count);
}

export function buildMlbGameStatusValidation(input: MLBGameStatusValidationInput): MLBGameStatusValidation {
  const abstractGameState = input.mlbStatus?.abstractGameState?.trim();
  const detailedState = input.mlbStatus?.detailedState?.trim();
  const normalized = input.mlbStatus?.normalized ?? normalizedStatus(abstractGameState, detailedState);
  const officialDate = dateOnly(input.mlbStatus?.officialDate ?? input.startTime);
  const marketDate = dateOnly(input.marketDate);
  const dateMatches = officialDate && marketDate ? officialDate === marketDate : undefined;
  const isPostponed = normalized === "POSTPONED";
  const isSuspended = normalized === "SUSPENDED";
  const isCancelled = normalized === "CANCELLED";
  const isFinal = normalized === "FINAL";
  const isLive = normalized === "LIVE";
  const isPreGame = normalized === "PRE_GAME";
  const available = Boolean(abstractGameState || detailedState || officialDate || marketDate || input.gameId || input.game);
  const warnings = uniqueStrings([
    !officialDate ? "Official MLB game date unavailable." : undefined,
    marketDate ? undefined : "Market date unavailable; date mismatch check is partial.",
    isLive ? "MLB game is already live; pregame betting is blocked." : undefined,
    isFinal ? "MLB game is final; official betting is blocked." : undefined,
    isPostponed ? "MLB game is postponed; official betting is blocked." : undefined,
    isSuspended ? "MLB game is suspended; official betting is blocked." : undefined,
    isCancelled ? "MLB game is cancelled; official betting is blocked." : undefined,
  ]);
  const gameStatusBlockReasons = uniqueStrings([
    isPostponed ? "Blocked: MLB game status is Postponed." : undefined,
    isSuspended ? "Blocked: MLB game status is Suspended." : undefined,
    isCancelled ? "Blocked: MLB game status is Cancelled." : undefined,
    isFinal ? "Blocked: MLB game status is Final." : undefined,
    isLive ? "Blocked: MLB game is already Live." : undefined,
    !isPreGame && !isLive && !isFinal && !isPostponed && !isSuspended && !isCancelled ? "Blocked: MLB game status is unavailable." : undefined,
    dateMatches === false ? "Blocked: MLB market date does not match MLB game date." : undefined,
  ]);

  return {
    available,
    gameId: input.gameId,
    game: input.game,
    mlbStatus: normalized,
    abstractGameState,
    detailedState,
    officialDate,
    marketDate,
    dateMatches,
    isGameActiveForBetting: isPreGame && gameStatusBlockReasons.length === 0,
    isPostponed,
    isSuspended,
    isCancelled,
    isFinal,
    isLive,
    isDateMismatch: dateMatches === false,
    gameStatusBlockReasons,
    warnings,
    source: "MLB StatsAPI schedule + Polymarket market date",
  };
}

export function buildMlbGameStatusValidationDiagnostics(validations: MLBGameStatusValidation[]): MLBGameStatusValidationDiagnostics {
  const reasonCounts = new Map<string, number>();
  let activeGames = 0;
  let blockedGames = 0;
  let postponedGames = 0;
  let suspendedGames = 0;
  let cancelledGames = 0;
  let finalGames = 0;
  let liveGames = 0;
  let dateMismatchGames = 0;
  let missingMarketDateGames = 0;

  for (const validation of validations) {
    if (validation.isGameActiveForBetting) activeGames += 1;
    else blockedGames += 1;
    if (validation.isPostponed) postponedGames += 1;
    if (validation.isSuspended) suspendedGames += 1;
    if (validation.isCancelled) cancelledGames += 1;
    if (validation.isFinal) finalGames += 1;
    if (validation.isLive) liveGames += 1;
    if (validation.isDateMismatch) dateMismatchGames += 1;
    if (!validation.marketDate) missingMarketDateGames += 1;
    for (const reason of validation.gameStatusBlockReasons) addReason(reasonCounts, reason, 1);
  }

  const warnings = uniqueStrings([
    validations.length === 0 ? "No MLB game status validations were generated." : undefined,
    blockedGames > 0 ? `${blockedGames} MLB game${blockedGames === 1 ? "" : "s"} are blocked by status validation.` : undefined,
    missingMarketDateGames > 0 ? `${missingMarketDateGames} MLB game${missingMarketDateGames === 1 ? "" : "s"} are missing a market date for full validation.` : undefined,
    dateMismatchGames > 0 ? `${dateMismatchGames} MLB game${dateMismatchGames === 1 ? "" : "s"} have a market date mismatch.` : undefined,
    validations.length > 0 && activeGames === 0 ? "No MLB rows are currently active for betting." : undefined,
  ]);

  return {
    available: validations.length > 0,
    status: validations.length === 0 ? "missing" : blockedGames > 0 ? "partial" : "available",
    totalGamesEvaluated: validations.length,
    activeGames,
    blockedGames,
    postponedGames,
    suspendedGames,
    cancelledGames,
    finalGames,
    liveGames,
    dateMismatchGames,
    missingMarketDateGames,
    gameStatusBlockReasons: Array.from(reasonCounts, ([reason, count]) => ({ reason, count }))
      .sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason))
      .slice(0, 8),
    warnings,
    generatedAt: new Date().toISOString(),
    source: "MLB StatsAPI schedule + Polymarket market date",
    officialPickEligible: false,
    officialEdgeAllowed: false,
    isPaperOnly: true,
    realMoneyDisabled: true,
  };
}
