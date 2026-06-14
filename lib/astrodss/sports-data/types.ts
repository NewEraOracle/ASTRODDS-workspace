import type { MLBGameStatusSnapshot, MLBGameStatusValidation } from "../mlb/game-status-validation";

export type AstroddsSport = "MLB" | "NFL" | "NBA" | "NHL" | "SOCCER" | "TENNIS" | "MMA" | "OTHER";

export type AstroddsSportFilter = "ALL" | AstroddsSport;

export type AstroddsDataStatus = "CONNECTED" | "PARTIAL" | "NOT_CONNECTED" | "DEMO_FALLBACK" | "WALLET_LED";

export type AstroddsDiagnosticStatus = "CONNECTED_SERVER" | "CONNECTED_BROWSER" | "CONNECTED" | "PARTIAL" | "FAILED" | "NOT_CONNECTED";

export type AstroddsSourceMode = "SERVER" | "BROWSER_FALLBACK" | "FAILED";

export type AstroddsLiveStatus = "PRE_GAME" | "LIVE" | "FINAL" | "UNKNOWN";

export type AstroddsBetType = "MONEYLINE" | "SPREAD" | "TOTAL" | "PROP" | "YES_NO" | "OTHER";

export type AstroddsDecision =
  | "ELITE"
  | "STRONG_BUY"
  | "BUY"
  | "WATCH"
  | "WAIT"
  | "AVOID"
  | "PROFIT_LOCK"
  | "CASH_OUT"
  | "HEDGE";

export type AstroddsConfidence = "ELITE" | "STRONG" | "MEDIUM" | "LOW" | "NO_BET";

export type AstroddsSourceStatus = AstroddsDataStatus;

export type AstroddsMarketStatus = "ACTIVE" | "PENDING" | "RESOLVED" | "CLOSED" | "UNKNOWN";

export type AstroddsEntryQuality = "EXCELLENT" | "GOOD" | "FAIR" | "POOR" | "NO_LIQUIDITY" | "STRETCHED" | "NO_ENTRY" | "UNKNOWN";

export type AstroddsOrderBookStatus = "EXCELLENT" | "GOOD" | "FAIR" | "POOR" | "NO_LIQUIDITY" | "NOT_CONNECTED";

export type AstroddsDataQuality = "HIGH" | "MEDIUM" | "LOW" | "VERY_LOW";

export type AstroddsScanStep =
  | "Pulling Polymarket markets"
  | "Pulling sport data"
  | "Pulling lineups"
  | "Pulling injuries"
  | "Pulling pitchers/goalies"
  | "Pulling weather"
  | "Matching games to markets"
  | "Running ASTRODDS decision engine"
  | "Ranking best picks";

export type AstroddsWalletRank = "NONE" | "DATA_ONLY" | "PROMISING_WATCH" | "GOLD_WALLET" | "DIAMOND_ELITE_WALLET";

export type AstroddsWeatherImpact = "NONE" | "LOW" | "MEDIUM" | "HIGH";

export type AstroddsSourceStatusMap = {
  polymarket: AstroddsSourceStatus;
  sportData: AstroddsSourceStatus;
  weather: AstroddsSourceStatus;
  lineups: AstroddsSourceStatus;
  injuries: AstroddsSourceStatus;
  keyPlayers: AstroddsSourceStatus;
  wallets: AstroddsSourceStatus;
};

export type AstroddsWeatherContext = {
  status: AstroddsSourceStatus;
  source?: string;
  temperatureF?: number;
  windMph?: number;
  windDirection?: number;
  precipitationProbability?: number;
  humidity?: number;
  impactScore: number;
  impact: AstroddsWeatherImpact;
  summary: string;
};

export type AstroddsInjuryContext = {
  status: AstroddsSourceStatus;
  source?: string;
  summary: string;
  keyAbsences?: string[];
};

export type AstroddsLineupContext = {
  status: AstroddsSourceStatus;
  source?: string;
  summary: string;
};

export type AstroddsWalletSupport = {
  status: AstroddsSourceStatus;
  rank: AstroddsWalletRank;
  supportingWallets: number;
  winRate?: number;
  realSettled?: number;
  sportsFocus?: number;
  buyingPressure?: number;
  summary: string;
};

export type AstroddsDecisionScore = {
  sportsData: number;
  marketPrice: number;
  liveGameState: number;
  walletIntelligence: number;
  riskManagement: number;
  total: number;
  entryQuality: AstroddsEntryQuality;
  missingDataWarnings: string[];
};

export type AstroddsProbabilityAssessment = {
  modelProbability: number;
  marketImpliedProbability: number;
  edge: number;
  expectedValue: number;
  dataQuality: AstroddsDataQuality;
  confidence: AstroddsConfidence;
  decision: AstroddsDecision;
  reasons: string[];
  warnings: string[];
};

export type AstroddsEdgeAssessment = {
  edgeScore: number;
  decision: AstroddsDecision;
  confidence: AstroddsConfidence;
  exactPick: string;
  simpleWhy: string;
  dataWarnings: string[];
  riskWarnings: string[];
  missingData: string[];
  recommendedAction: string;
  modelProbability: number;
  marketImpliedProbability: number;
  edge: number;
  expectedValue: number;
  dataQuality: AstroddsDataQuality;
  sportsMatchupScore: number;
  marketValueScore: number;
  orderBookScore: number;
  riskScore: number;
  walletSupportScore: number;
};

export type AstroddsOrderBookLevel = {
  price: number;
  size: number;
};

export type AstroddsOrderBook = {
  tokenId: string;
  bids: AstroddsOrderBookLevel[];
  asks: AstroddsOrderBookLevel[];
  lastTradePrice?: number;
  sourceUrl?: string;
};

export type AstroddsOrderBookMetrics = {
  status: AstroddsOrderBookStatus;
  sourceMode?: AstroddsSourceMode;
  bestBid?: number;
  bestAsk?: number;
  midpoint?: number;
  spread?: number;
  spreadPercent?: number;
  lastTradePrice?: number;
  depthAtBestAsk: number;
  depthAtBestBid: number;
  depthWithin1Percent: number;
  depthWithin3Percent: number;
  estimatedShares: number;
  estimatedAverageFillPrice?: number;
  estimatedSlippage?: number;
  fillStatus: "OK" | "PARTIAL" | "NOT_ENOUGH_LIQUIDITY" | "UNKNOWN";
  remainingUnfilledAmount: number;
  liquidityScore: number;
  orderBookScore: number;
  entryQuality: AstroddsEntryQuality;
  summary: string;
  sourceUrl?: string;
  error?: string;
};

export type AstroddsMarketScan = {
  marketId: string;
  conditionId?: string;
  assetId?: string;
  marketTitle: string;
  outcomes: string[];
  betType: AstroddsBetType;
  pick: string;
  currentPrice: number;
  entryPrice?: number;
  volume?: number;
  liquidity?: number;
  priceMovement?: number;
  spread?: number;
  bestBid?: number;
  bestAsk?: number;
  orderBook?: AstroddsOrderBookMetrics;
  marketAgeHours?: number;
  timeToStartHours?: number;
  marketDate?: string;
  gameDate?: string;
  gameStatusValidation?: MLBGameStatusValidation;
  status: AstroddsMarketStatus;
  category?: string;
  walletSupport?: AstroddsWalletSupport;
  score?: AstroddsDecisionScore;
  edge?: AstroddsEdgeAssessment;
  probability?: AstroddsProbabilityAssessment;
  decision?: AstroddsDecision;
  confidence?: AstroddsConfidence;
  why?: string;
  matchReason?: string;
  unmatchedReason?: string;
  sourceUrl?: string;
};


export type AstroddsMlbDataQualityGrade = "A" | "B" | "C" | "D" | "F";

export type AstroddsMlbPitcherContext = {
  id?: number;
  name?: string;
  handedness?: string;
  era?: number;
  whip?: number;
  strikeOuts?: number;
  wins?: number;
  losses?: number;
  sourceStatus: AstroddsSourceStatus;
  summary: string;
};

export type AstroddsMlbTeamRecord = {
  teamId?: number;
  teamName: string;
  wins?: number;
  losses?: number;
  winningPercentage?: number;
  streak?: string;
  recentGames?: number;
  recentWins?: number;
  recentLosses?: number;
  recentRunsFor?: number;
  recentRunsAgainst?: number;
  sourceStatus: AstroddsSourceStatus;
  summary: string;
};

export type AstroddsMlbModelPick = {
  modelLeanSide: "HOME" | "AWAY" | "WAIT";
  modelLeanTeam?: string;
  modelConfidence: number;
  modelScore: number;
  dataQuality: AstroddsMlbDataQualityGrade;
  dataQualityScore: number;
  pitcherScore: number;
  lineupScore: number;
  injuryScore: number;
  teamFormScore: number;
  weatherScore: number;
  modelReason: string;
  missingDataWarnings: string[];
  officialBetBlockedReason: string;
  action: "WAIT_FOR_ODDS" | "WAIT";
};

export type AstroddsMlbGameContext = {
  gamePk: number;
  awayTeamId?: number;
  homeTeamId?: number;
  awayRecord?: AstroddsMlbTeamRecord;
  homeRecord?: AstroddsMlbTeamRecord;
  awayPitcher?: AstroddsMlbPitcherContext;
  homePitcher?: AstroddsMlbPitcherContext;
  statsApiHealth: {
    schedule: AstroddsSourceStatus;
    standings: AstroddsSourceStatus;
    recentForm: AstroddsSourceStatus;
    pitcherDetails: AstroddsSourceStatus;
    linescore: AstroddsSourceStatus;
  };
};
export type AstroddsGameScan = {
  id: string;
  sport: AstroddsSport;
  league?: string;
  game: string;
  homeTeam?: string;
  awayTeam?: string;
  players?: string[];
  startTime?: string;
  liveStatus: AstroddsLiveStatus;
  score?: string;
  period?: string;
  venue?: string;
  mlbStatus?: MLBGameStatusSnapshot;
  gameStatusValidation?: MLBGameStatusValidation;
  weather?: AstroddsWeatherContext;
  injuries?: AstroddsInjuryContext;
  lineups?: AstroddsLineupContext;
  keyContext: string[];
  keyPlayerStatus: string;
  markets: AstroddsMarketScan[];
  marketConnected?: boolean;
  dataStatus: AstroddsDataStatus;
  source: string;
  mlbContext?: AstroddsMlbGameContext;
  modelPick?: AstroddsMlbModelPick;
  unmatchedReason?: string;
};

export type AstroddsScanResult = {
  sport: AstroddsSportFilter;
  generatedAt: string;
  lastScanTime: string;
  sourceStatus: AstroddsSourceStatusMap;
  diagnostics: AstroddsScanDiagnostics;
  games: AstroddsGameScan[];
  bestPicks: Array<AstroddsGameScan & { market: AstroddsMarketScan }>;
  warnings: string[];
};

export type AstroddsSourceDiagnostic = {
  sourceLabel: string;
  endpointLabel: string;
  status: "OK" | "FAILED";
  httpStatus?: number;
  timedOut: boolean;
  sanitizedUrl: string;
  errorMessage?: string;
  retryCount: number;
};
export type AstroddsScanDiagnostics = {
  gameStatusValidationDiagnostics?: {
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
  polymarket: {
    status: AstroddsDiagnosticStatus;
    sourceMode?: AstroddsSourceMode;
    marketsFetched: number;
    sportsMarketsDetected: number;
    marketsMatchedToGames: number;
    totalGammaMarketsScanned?: number;
    rawEventsFetched?: number;
    rawMarketsFetched?: number;
    rejectedNonMlbMarkets?: number;
    acceptedMlbMarkets?: number;
    mlbMarketsDetected?: number;
    singleGameMlbMarketsDetected?: number;
    rejectedBySportCategory?: number;
    rejectedByTeamAlias?: number;
    rejectedByDate?: number;
    rejectedBySingleGameFilter?: number;
    queryStrategiesUsed?: string[];
    teamSearchQueriesAttempted?: string[];
    futuresRejected?: number;
    wrongSportsRejected?: number;
    noMlbTeamMatchRejected?: number;
    unclearYesNoRejected?: number;
    rejectedMarkets?: Array<{ title: string; rejectedReason: string }>;
    rawMarketSamples?: string[];
    mlbCandidateMarketSamples?: string[];
    matchedMarketSamples?: string[];
    rejectionReasonCounts?: Array<{ reason: string; count: number }>;
    error?: string;
    sourceUrl?: string;
  };
  sportApi: {
    sport: AstroddsSportFilter;
    status: AstroddsDiagnosticStatus;
    sourceMode?: AstroddsSourceMode;
    gamesFetched: number;
    uniqueGamesFetched?: number;
    duplicateGamesRemoved?: number;
    probablePitchersFound: number;
    venuesFound: number;
    error?: string;
    sourceUrl?: string;
  };
  weather: {
    status: AstroddsDiagnosticStatus;
    sourceMode?: AstroddsSourceMode;
    gamesWithMappedCityOrStadium: number;
    weatherResultsFetched: number;
    error?: string;
    sourceUrl?: string;
  };
  matching: {
    status: AstroddsDiagnosticStatus;
    sourceMode?: AstroddsSourceMode;
    gamesCount: number;
    polymarketMarketsCount: number;
    matchedMarketsCount: number;
    matchedGamesCount: number;
    unmatchedMarkets: string[];
    unmatchedGames: string[];
    unmatchedMarketReasons: Array<{ market: string; unmatchedReason: string }>;
    unmatchedGameReasons: Array<{ game: string; unmatchedReason: string }>;
    unmatchedReasons: Array<{ type: "game" | "market"; name: string; unmatchedReason: string }>;
    error?: string;
  };
  orderBook: {
    status: AstroddsDiagnosticStatus;
    sourceMode?: AstroddsSourceMode;
    orderBooksRequested: number;
    orderBooksFetched: number;
    orderBooksFailed: number;
    sourceUrl?: string;
    error?: string;
    failedTokenIds?: string[];
  };
  lastErrors: string[];
  sourceDiagnostics?: AstroddsSourceDiagnostic[];
};

export type AstroddsApiTestSource = "polymarket" | "mlb" | "weather" | "matching";

export type AstroddsApiTestResult = {
  source: AstroddsApiTestSource;
  status: AstroddsDiagnosticStatus;
  sourceUrl?: string;
  httpStatus?: number;
  count?: number;
  sample?: unknown;
  error?: string;
  testedAt: string;
};

export type RawPolymarketMarket = {
  marketId: string;
  conditionId?: string;
  assetIds: string[];
  title: string;
  slug?: string;
  category?: string;
  outcomes: string[];
  outcomePrices: number[];
  volume?: number;
  liquidity?: number;
  active?: boolean;
  closed?: boolean;
  acceptingOrders?: boolean;
  startDate?: string;
  endDate?: string;
  createdAt?: string;
  eventTitle?: string;
  eventSlug?: string;
  marketDate?: string;
  gameDate?: string;
  sport?: AstroddsSport | "OTHER";
  sourceUrl?: string;
  rejectedReason?: string;
};

export type SportScannerOptions = {
  sport: AstroddsSportFilter;
  signal?: AbortSignal;
};
