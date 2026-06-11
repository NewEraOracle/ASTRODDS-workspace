import { loadPolymarketMlbMarketsCache, writePolymarketMlbMarketsCache, type PolymarketMlbCacheStatus } from "./polymarket-mlb-market-cache";
import { MLB_TEAMS, mlbTeamHits } from "./mlb-teams";
import { normalizeText, safeArray, safeNumber } from "./normalize";
import { POLYMARKET_GAMMA_BASE_URL, type GammaEvent, type GammaMarket } from "./polymarket";

export type PolymarketMlbMoneylineStatus = "CONNECTED" | "PARTIAL" | "FAILED" | "NOT_CONNECTED";

export type PolymarketMlbSourceDiagnostic = {
  source: "Polymarket Gamma";
  endpointLabel: string;
  status: "CONNECTED" | "FAILED" | "TIMEOUT";
  httpStatus?: number;
  timeout: boolean;
  sanitizedUrl: string;
  error?: string;
  responseSnippet?: string;
  retryCount: number;
};

export type PolymarketMlbOutcomeProbability = {
  outcome: string;
  tokenId?: string;
  price?: number;
  marketProbability: number | null;
  mappedTeam?: string;
};

export type PolymarketMlbMoneylineMarket = {
  marketId: string;
  conditionId?: string;
  question: string;
  title: string;
  slug?: string;
  sourceUrl?: string;
  eventTitle?: string;
  eventSlug?: string;
  category?: string;
  detectedHomeTeam?: string;
  detectedAwayTeam?: string;
  detectedTeams: string[];
  outcomes: string[];
  clobTokenIds: string[];
  outcomeProbabilities: PolymarketMlbOutcomeProbability[];
  marketProbability: number | null;
  liquidity?: number;
  volume?: number;
  endDate?: string;
  gameDate?: string;
  active: boolean;
  closed: boolean;
  warnings: string[];
};

export type PolymarketMlbMoneylineDiscoveryResult = {
  status: PolymarketMlbMoneylineStatus;
  marketPricesConnected: boolean;
  supportedMarkets: ["moneyline"];
  disabledMarkets: ["runline"];
  futureMarkets: ["total_runs"];
  markets: PolymarketMlbMoneylineMarket[];
  sourceDiagnostics: PolymarketMlbSourceDiagnostic[];
  warnings: string[];
  generatedAt: string;
  cacheUsed: boolean;
  cacheStatus: PolymarketMlbCacheStatus;
  cacheAgeSeconds?: number;
  cacheGeneratedAt?: string;
};

type FetchJsonResult = {
  data: unknown[];
  diagnostic: PolymarketMlbSourceDiagnostic;
};

const DEFAULT_TIMEOUT_MS = 7500;
const REQUEST_LIMIT = 100;

const wrongSportPatterns = [
  /\bnba\b/i,
  /\bnhl\b/i,
  /\bnfl\b/i,
  /\bstanley cup\b/i,
  /\bnba finals\b/i,
  /\bsuper bowl\b/i,
  /\bhockey\b/i,
  /\bbasketball\b/i,
  /\bfootball\b/i,
  /\belection\b/i,
  /\bpresident\b/i,
  /\bbitcoin\b/i,
  /\bcrypto\b/i,
  /\bstock\b/i,
  /\bipo\b/i,
];

const futuresPatterns = [
  /\bworld series\b/i,
  /\bchampionship\b/i,
  /\bchampion\b/i,
  /\bdivision\b/i,
  /\bplayoffs?\b/i,
  /\bmvp\b/i,
  /\bcy young\b/i,
  /\baward\b/i,
  /\bseason wins?\b/i,
  /\bpennant\b/i,
];

const disabledMarketPatterns = [
  /\brun line\b/i,
  /\bspread\b/i,
  /[+-]\s*\d+(?:\.\d+)?/,
];

const futureSecondaryPatterns = [
  /\bo\s*\/\s*u\b/i,
  /\bover\s*\/\s*under\b/i,
  /\bover\b/i,
  /\bunder\b/i,
  /\btotal runs?\b/i,
  /\btotal\b/i,
];

const moneylineContextPatterns = [
  /\bwill\b.*\bbeat\b/i,
  /\bwill\b.*\bwin\b/i,
  /\bwho will win\b/i,
  /\bgame winner\b/i,
  /\bmoneyline\b/i,
  /\bto win\b/i,
  /\bvs\.?\b/i,
  /\bversus\b/i,
  /\s@\s/,
];

function polymarketUrl(pathname: "/events" | "/markets", query: string) {
  const url = new URL(pathname, POLYMARKET_GAMMA_BASE_URL);
  url.searchParams.set("active", "true");
  url.searchParams.set("closed", "false");
  url.searchParams.set("limit", String(REQUEST_LIMIT));
  url.searchParams.set("order", "volume_24hr");
  url.searchParams.set("ascending", "false");
  url.searchParams.set("q", query);
  return url;
}

function sanitizedUrl(url: URL) {
  const copy = new URL(url.toString());
  return `${copy.origin}${copy.pathname}?${copy.searchParams.toString()}`;
}

function responseSnippet(text: string) {
  return text.replace(/\s+/g, " ").slice(0, 240);
}

async function fetchJsonArray(url: URL, endpointLabel: string, timeoutMs: number): Promise<FetchJsonResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const baseDiagnostic: Omit<PolymarketMlbSourceDiagnostic, "status" | "timeout"> = {
    source: "Polymarket Gamma",
    endpointLabel,
    sanitizedUrl: sanitizedUrl(url),
    retryCount: 0,
  };

  try {
    const response = await fetch(url, {
      signal: controller.signal,
      cache: "no-store",
      headers: { accept: "application/json" },
    });
    const text = await response.text();

    if (!response.ok) {
      return {
        data: [],
        diagnostic: {
          ...baseDiagnostic,
          status: "FAILED",
          httpStatus: response.status,
          timeout: false,
          error: `HTTP ${response.status}`,
          responseSnippet: responseSnippet(text),
        },
      };
    }

    const parsed = JSON.parse(text) as unknown;
    return {
      data: Array.isArray(parsed) ? parsed : [],
      diagnostic: {
        ...baseDiagnostic,
        status: "CONNECTED",
        httpStatus: response.status,
        timeout: false,
      },
    };
  } catch (error) {
    const timeout = error instanceof Error && error.name === "AbortError";
    return {
      data: [],
      diagnostic: {
        ...baseDiagnostic,
        status: timeout ? "TIMEOUT" : "FAILED",
        timeout,
        error: error instanceof Error ? error.message : "Unknown Polymarket fetch failure",
      },
    };
  } finally {
    clearTimeout(timeout);
  }
}

function marketSearchTerms() {
  const terms = new Set<string>(["MLB", "baseball", "Major League Baseball", "MLB moneyline", "MLB game winner"]);
  for (const team of MLB_TEAMS) {
    terms.add(`${team.nickname} MLB`);
    terms.add(`${team.canonicalName} baseball`);
  }
  return Array.from(terms).slice(0, 70);
}

function tagText(tags: GammaEvent["tags"] | GammaMarket["tags"]) {
  if (!Array.isArray(tags)) return "";
  return tags
    .map((tag) => (typeof tag === "string" ? tag : `${tag.label ?? ""} ${tag.name ?? ""} ${tag.slug ?? ""}`))
    .join(" ");
}

function marketText(market: GammaMarket, event?: GammaEvent) {
  return [
    event?.title,
    market.question,
    market.title,
    event?.category,
    market.category,
    tagText(event?.tags),
    tagText(market.tags),
    safeArray<string>(market.outcomes).join(" "),
  ]
    .filter(Boolean)
    .join(" ");
}

function isWrongSport(text: string) {
  const hasMlbTeam = mlbTeamHits(text).length > 0;
  if (hasMlbTeam && /\bbaseball\b|\bmlb\b|major league baseball/i.test(text)) return false;
  return wrongSportPatterns.some((pattern) => pattern.test(text));
}

function isMoneylineCandidate(text: string) {
  const teamHits = mlbTeamHits(text);
  const uniqueTeams = Array.from(new Set(teamHits.map((hit) => hit.profile.canonicalName)));
  if (uniqueTeams.length < 2) return false;
  if (isWrongSport(text)) return false;
  if (futuresPatterns.some((pattern) => pattern.test(text))) return false;
  if (disabledMarketPatterns.some((pattern) => pattern.test(text))) return false;
  if (futureSecondaryPatterns.some((pattern) => pattern.test(text))) return false;
  return moneylineContextPatterns.some((pattern) => pattern.test(text)) || /\bwin\b/i.test(text);
}

function orderedTeams(text: string) {
  const normalized = normalizeText(text);
  const seen = new Map<string, { team: string; index: number }>();
  for (const hit of mlbTeamHits(text)) {
    const index = normalized.indexOf(hit.alias);
    const existing = seen.get(hit.profile.canonicalName);
    if (!existing || (index >= 0 && index < existing.index)) {
      seen.set(hit.profile.canonicalName, { team: hit.profile.canonicalName, index: index >= 0 ? index : Number.MAX_SAFE_INTEGER });
    }
  }
  return Array.from(seen.values()).sort((a, b) => a.index - b.index).map((item) => item.team);
}

function sourceUrlFor(market: GammaMarket, event?: GammaEvent) {
  const slug = event?.slug ?? market.slug;
  return slug ? `https://polymarket.com/event/${slug}` : undefined;
}

function probabilityForOutcome(outcome: string, index: number, teams: string[], prices: number[], tokenIds: string[]) {
  const price = prices[index];
  const normalizedOutcome = normalizeText(outcome);
  let mappedTeam = teams.find((team) => normalizeText(team) === normalizedOutcome || normalizeText(team).includes(normalizedOutcome) || normalizedOutcome.includes(normalizeText(team)));

  if (!mappedTeam && teams.length >= 2 && /^(yes|no)$/.test(normalizedOutcome)) {
    mappedTeam = normalizedOutcome === "yes" ? teams[0] : teams[1];
  }

  return {
    outcome,
    tokenId: tokenIds[index],
    price,
    marketProbability: typeof price === "number" && Number.isFinite(price) ? Math.max(0, Math.min(1, price)) : null,
    mappedTeam,
  } satisfies PolymarketMlbOutcomeProbability;
}

function normalizeMarket(market: GammaMarket, event?: GammaEvent): PolymarketMlbMoneylineMarket | undefined {
  const text = marketText(market, event);
  if (!isMoneylineCandidate(text)) return undefined;

  const teams = orderedTeams(text).slice(0, 2);
  const outcomes = safeArray<string>(market.outcomes).map(String);
  const prices = safeArray<unknown>(market.outcomePrices).map((value) => safeNumber(value)).filter((value): value is number => typeof value === "number");
  const tokenIds = safeArray<string>(market.clobTokenIds).map(String);
  const outcomeProbabilities = (outcomes.length ? outcomes : [teams[0] ?? "Yes", teams[1] ?? "No"]).map((outcome, index) => probabilityForOutcome(outcome, index, teams, prices, tokenIds));
  const firstProbability = outcomeProbabilities.find((outcome) => outcome.marketProbability !== null)?.marketProbability ?? null;
  const question = market.question ?? market.title ?? event?.title ?? "Untitled MLB moneyline market";
  const warnings: string[] = [];

  if (firstProbability === null) warnings.push("Outcome price missing; market probability left null.");
  if (!tokenIds.length) warnings.push("CLOB token IDs missing; order book diagnostics unavailable from this discovery response.");
  if (teams.length < 2) warnings.push("Detected fewer than two MLB teams after alias filtering.");

  return {
    marketId: String(market.id ?? market.conditionId ?? market.slug ?? question),
    conditionId: market.conditionId,
    question,
    title: market.title ?? question,
    slug: market.slug,
    sourceUrl: sourceUrlFor(market, event),
    eventTitle: event?.title,
    eventSlug: event?.slug,
    category: market.category ?? event?.category,
    detectedAwayTeam: teams[0],
    detectedHomeTeam: teams[1],
    detectedTeams: teams,
    outcomes,
    clobTokenIds: tokenIds,
    outcomeProbabilities,
    marketProbability: firstProbability,
    liquidity: safeNumber(market.liquidityNum ?? market.liquidity ?? event?.liquidity),
    volume: safeNumber(market.volumeNum ?? market.volume ?? event?.volume),
    endDate: market.endDate ?? event?.endDate,
    gameDate: market.startDate ?? event?.startDate ?? market.endDate ?? event?.endDate,
    active: market.active ?? event?.active ?? false,
    closed: market.closed ?? event?.closed ?? false,
    warnings,
  };
}

function dedupeMarkets(markets: PolymarketMlbMoneylineMarket[]) {
  const seen = new Set<string>();
  return markets.filter((market) => {
    const key = `${market.marketId}|${market.conditionId ?? ""}|${market.question}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export async function discoverPolymarketMlbMoneylineMarkets(options: { timeoutMs?: number; cacheFreshnessSeconds?: number } = {}): Promise<PolymarketMlbMoneylineDiscoveryResult> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const terms = marketSearchTerms();
  const eventRequests = terms.map((term) => fetchJsonArray(polymarketUrl("/events", term), `Gamma events: ${term}`, timeoutMs));
  const marketRequests = terms.map((term) => fetchJsonArray(polymarketUrl("/markets", term), `Gamma markets: ${term}`, timeoutMs));
  const results = await Promise.all([...eventRequests, ...marketRequests]);
  const diagnostics = results.map((result) => result.diagnostic);
  const events = results.slice(0, eventRequests.length).flatMap((result) => result.data as GammaEvent[]);
  const directMarkets = results.slice(eventRequests.length).flatMap((result) => result.data as GammaMarket[]);

  const eventMarkets = events.flatMap((event) => (event.markets ?? []).map((market) => normalizeMarket(market, event))).filter(Boolean) as PolymarketMlbMoneylineMarket[];
  const normalizedDirectMarkets = directMarkets.map((market) => normalizeMarket(market)).filter(Boolean) as PolymarketMlbMoneylineMarket[];
  const markets = dedupeMarkets([...eventMarkets, ...normalizedDirectMarkets]).sort((a, b) => (b.volume ?? 0) - (a.volume ?? 0));
  const connectedFetches = diagnostics.filter((diagnostic) => diagnostic.status === "CONNECTED").length;
  const failedFetches = diagnostics.length - connectedFetches;
  const warnings = new Set<string>();

  if (!markets.length) warnings.add("No active MLB Moneyline/Game Winner markets found through public Polymarket Gamma search.");
  for (const market of markets) for (const warning of market.warnings) warnings.add(warning);
  if (failedFetches) warnings.add(`${failedFetches} Polymarket discovery requests failed or timed out.`);

  const status: PolymarketMlbMoneylineStatus = connectedFetches === 0
    ? "FAILED"
    : failedFetches || !markets.length
      ? "PARTIAL"
      : "CONNECTED";

  const generatedAt = new Date().toISOString();
  const liveResult: PolymarketMlbMoneylineDiscoveryResult = {
    status,
    marketPricesConnected: markets.length > 0,
    supportedMarkets: ["moneyline"],
    disabledMarkets: ["runline"],
    futureMarkets: ["total_runs"],
    markets,
    sourceDiagnostics: diagnostics,
    warnings: Array.from(warnings),
    generatedAt,
    cacheUsed: false,
    cacheStatus: "not_used",
  };

  if (liveResult.marketPricesConnected) {
    await writePolymarketMlbMarketsCache({
      generatedAt: liveResult.generatedAt,
      marketPricesConnected: liveResult.marketPricesConnected,
      markets: liveResult.markets,
      warnings: liveResult.warnings,
      sourceDiagnostics: liveResult.sourceDiagnostics,
    });
    return liveResult;
  }

  if (liveResult.status !== "FAILED") return liveResult;

  const cached = await loadPolymarketMlbMarketsCache({ freshnessSeconds: options.cacheFreshnessSeconds });
  if (!cached.snapshot) {
    return {
      ...liveResult,
      markets: [],
      marketPricesConnected: false,
      warnings: [],
      cacheUsed: false,
      cacheStatus: cached.metadata.cacheStatus,
      cacheAgeSeconds: cached.metadata.cacheAgeSeconds,
      cacheGeneratedAt: cached.metadata.cacheGeneratedAt,
    };
  }

  return {
    ...liveResult,
    status: "PARTIAL",
    marketPricesConnected: true,
    markets: cached.snapshot.markets,
    warnings: ["Live Polymarket discovery failed; using fresh cached MLB moneyline market diagnostics snapshot.", ...cached.snapshot.warnings],
    cacheUsed: true,
    cacheStatus: cached.metadata.cacheStatus,
    cacheAgeSeconds: cached.metadata.cacheAgeSeconds,
    cacheGeneratedAt: cached.metadata.cacheGeneratedAt,
  };
}
