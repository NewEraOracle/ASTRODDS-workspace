import type { AstroddsBetType, AstroddsOrderBookMetrics } from "../sports-data/types";
import type { WhaleMarketCategory, WhaleSportCategory } from "./market-classifier";

export type WhaleWalletRank = "WHALE_WATCH" | "DIAMOND_CANDIDATE" | "ELITE_TRADER" | "DATA_ONLY";
export type WalletSourceStatus = "CONNECTED" | "PARTIAL" | "FAILED" | "NOT_CONNECTED";
export type WalletPositionStatus = "OPEN" | "CLOSED" | "WON" | "LOST" | "VOID" | "UNKNOWN";
export type WalletMarketType = AstroddsBetType | "FUTURE";
export type LimitEntryDisciplineLabel = "DISCIPLINED_ENTRY" | "MIXED_ENTRY" | "CHASES_PRICE" | "UNKNOWN";
export type HoldToResolutionLabel = "HOLDS_TO_RESOLUTION" | "MIXED_EXIT_AND_HOLD" | "ACTIVE_TRADER" | "UNKNOWN";
export type CopyabilityStatus =
  | "COPYABLE_NOW"
  | "NEAR_WHALE_ENTRY"
  | "WATCH_ONLY"
  | "STALE_ENTRY"
  | "TOO_LATE"
  | "NO_LIQUIDITY"
  | "CONFLICT"
  | "UNKNOWN";
export type WhaleConsensusLabel =
  | "NO_WHALE_SIGNAL"
  | "SINGLE_WHALE_ACTIVITY"
  | "MULTI_WHALE_CONFIRMATION"
  | "DIAMOND_CONSENSUS"
  | "CONFLICTED_WHALES"
  | "STALE_CONSENSUS";
export type WhaleSignalType =
  | "MODEL_ONLY"
  | "WHALE_ONLY_WATCH"
  | "WHALE_CONFIRMED"
  | "MULTI_WHALE_CONFIRMED"
  | "MODEL_WHALE_ORDERBOOK_ALIGNED"
  | "STALE_WHALE_ENTRY"
  | "CONFLICT";

export type KnownWhaleWallet = {
  handle: string;
  profileUrl: string;
  rank: WhaleWalletRank;
  source: "manual_polymarket_research";
  notes: string;
};

export type WalletActivity = {
  id: string;
  handle: string;
  address?: string;
  marketId?: string;
  conditionId?: string;
  assetId?: string;
  marketTitle?: string;
  side?: string;
  outcome?: string;
  price?: number;
  amount?: number;
  transactionHash?: string;
  timestamp?: string;
  rawType?: string;
};

export type WalletPosition = {
  id: string;
  handle: string;
  address?: string;
  marketId?: string;
  conditionId?: string;
  assetId?: string;
  sport?: string;
  category?: WhaleMarketCategory;
  sportCategory?: WhaleSportCategory;
  marketTitle: string;
  marketType: WalletMarketType;
  side: string;
  outcome: string;
  avgEntryPrice?: number;
  currentPrice?: number;
  shares?: number;
  positionValue?: number;
  realizedPnl?: number;
  unrealizedPnl?: number;
  status: WalletPositionStatus;
  createdAt?: string;
  updatedAt?: string;
  resolvedAt?: string;
};

export type WalletProfile = {
  handle: string;
  address?: string;
  profileUrl: string;
  totalPnl?: number;
  totalVolume?: number;
  predictions?: number;
  portfolioValue?: number;
  biggestWin?: number;
  joinedAt?: string;
  openPositions: WalletPosition[];
  closedPositions: WalletPosition[];
  activity: WalletActivity[];
  sourceStatus: WalletSourceStatus;
  error?: string;
  diagnostics?: WalletProfileDiagnostics;
};

export type WalletFetchDiagnostic = {
  label: "profile" | "activity" | "openPositions" | "closedPositions";
  resolved: boolean;
  sourceUrl?: string;
  httpStatus?: number;
  status: WalletSourceStatus;
  count?: number;
  error?: string;
  responseTextSnippet?: string;
  tlsFallback?: boolean;
};

export type WalletProfileDiagnostics = {
  handle: string;
  profileUrl: string;
  address?: string;
  profileResolved: boolean;
  activityResolved: boolean;
  openPositionsResolved: boolean;
  closedPositionsResolved: boolean;
  attemptedUrls: string[];
  checks: WalletFetchDiagnostic[];
};

export type WhaleStrategyMetrics = {
  handle: string;
  totalPositions: number;
  openPositions: number;
  closedPositions: number;
  resolvedWins: number;
  resolvedLosses: number;
  voids: number;
  pendingPositions: number;
  winRate: number;
  roi: number;
  totalVolume: number;
  averageBetSize: number;
  biggestBet: number;
  sportFocusPercent: number;
  sportFocus?: string;
  singleGameRatio: number;
  futuresRatio: number;
  marketTypeBreakdown: Record<string, number>;
  averageEntryPrice?: number;
  averageCurrentPrice?: number;
  averagePriceMovementAfterEntry?: number;
  averageHoldingTimeHours?: number;
  duplicateTradesRemoved: number;
  limitEntryDiscipline: LimitEntryDisciplineLabel;
  holdToResolution: HoldToResolutionLabel;
  copyabilityScore: CopyabilityStatus;
  lastScanned: string;
  nextRescan: string;
};

export type WhalePositionCopyability = {
  positionId: string;
  handle: string;
  marketTitle: string;
  side: string;
  whaleAvgEntry?: number;
  currentPrice?: number;
  currentBestAsk?: number;
  spread?: number;
  enoughLiquidityForPaperTrade: boolean;
  priceDeltaFromWhaleEntry?: number;
  timeSinceWhaleEntryHours?: number;
  status: CopyabilityStatus;
  reason: string;
};

export type WhaleConsensusSignal = {
  id: string;
  sport?: string;
  marketTitle: string;
  marketId?: string;
  conditionId?: string;
  assetId?: string;
  side: string;
  walletsOnSameSide: string[];
  walletsOnOppositeSide: string[];
  totalWhalePositionValue: number;
  averageWhaleEntry?: number;
  currentPrice?: number;
  priceDeltaFromWhaleAverage?: number;
  consensusStrength: WhaleConsensusLabel;
  conflictingWhales: string[];
  copyabilityStatus: CopyabilityStatus;
  signalType: WhaleSignalType;
  orderBook?: AstroddsOrderBookMetrics;
};

export type WalletScanResult = {
  profiles: WalletProfile[];
  strategyMetrics: WhaleStrategyMetrics[];
  activePositions: WalletPosition[];
  closedPositions: WalletPosition[];
  copyability: WhalePositionCopyability[];
  consensus: WhaleConsensusSignal[];
  sourceStatus: WalletSourceStatus;
  errors: string[];
  diagnostics: WalletProfileDiagnostics[];
  scannedAt: string;
};

export type WhaleOnlySignal = {
  signalKey: string;
  signalType: "WHALE_ONLY_PUBLIC_SIGNAL";
  whale: string;
  address?: string;
  category: WhaleMarketCategory;
  sport?: WhaleSportCategory;
  marketId?: string;
  conditionId?: string;
  assetId?: string;
  market: string;
  marketType: WalletMarketType | "OUTRIGHT";
  side: string;
  outcome: string;
  whaleEntryPrice?: number;
  currentPrice?: number;
  priceDelta?: number;
  positionValue?: number;
  shares?: number;
  status: WalletPositionStatus;
  copyability: CopyabilityStatus;
  copyabilityReason: string;
  orderBookStatus: string;
  orderBook?: AstroddsOrderBookMetrics;
  createdAt?: string;
  updatedAt?: string;
  telegramStatus: "READY" | "DISABLED" | "NOT_CONFIGURED" | "MISSING_CHAT_ID" | "NOT_QUALIFIED" | "DUPLICATE" | "SENT" | "FAILED";
  telegramReason: string;
};
