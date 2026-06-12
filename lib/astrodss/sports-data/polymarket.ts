import { setMaxListeners } from "node:events";

import type { AstroddsDiagnosticStatus, AstroddsGameScan, AstroddsMarketScan, AstroddsScanDiagnostics, AstroddsSportFilter, RawPolymarketMarket } from "./types";
import { findMlbTeamProfile, mlbTeamHits } from "./mlb-teams";
import { hydrateMarketsWithOrderBooks } from "./orderbook";
import { detectSport, inferBetType, inferMarketStatus, normalizeText, safeArray, safeNumber } from "./normalize";

export const POLYMARKET_GAMMA_BASE_URL = "https://gamma-api.polymarket.com";
const POLYMARKET_GAMMA_FETCH_TIMEOUT_MS = 7500;

export type GammaEvent = {
  id?: string | number;
  title?: string;
  slug?: string;
  category?: string;
  volume?: string | number;
  liquidity?: string | number;
  active?: boolean;
  closed?: boolean;
  startDate?: string;
  endDate?: string;
  createdAt?: string;
  tags?: Array<{ label?: string; name?: string; slug?: string }> | string[];
  markets?: GammaMarket[];
};

export type GammaMarket = {
  id?: string | number;
  question?: string;
  title?: string;
  slug?: string;
  conditionId?: string;
  clobTokenIds?: string[] | string;
  outcomes?: string[] | string;
  outcomePrices?: number[] | string[] | string;
  currentPrice?: number | string;
  price?: number | string;
  bestBid?: number | string;
  bestAsk?: number | string;
  lastTradePrice?: number | string;
  volume?: string | number;
  volumeNum?: string | number;
  liquidity?: string | number;
  liquidityNum?: string | number;
  active?: boolean;
  closed?: boolean;
  acceptingOrders?: boolean;
  startDate?: string;
  endDate?: string;
  createdAt?: string;
  category?: string;
  tags?: Array<{ label?: string; name?: string; slug?: string }> | string[];
};

export function polymarketSportQueryTerms(sport: AstroddsSportFilter) {
  switch (sport) {
    case "MLB":
      return ["MLB", "baseball", "Major League Baseball"];
    case "NFL":
      return ["NFL"];
    case "NBA":
      return ["NBA"];
    case "NHL":
      return ["NHL"];
    case "SOCCER":
      return ["soccer", "Premier League", "MLS"];
    case "TENNIS":
      return ["tennis", "ATP", "WTA"];
    case "MMA":
      return ["UFC", "MMA"];
    case "ALL":
    default:
      return ["MLB", "NFL", "NBA", "NHL", "soccer", "tennis", "UFC"];
  }
}

export function polymarketEventsUrl(query: string) {
  const url = new URL("/events", POLYMARKET_GAMMA_BASE_URL);
  url.searchParams.set("active", "true");
  url.searchParams.set("closed", "false");
  url.searchParams.set("limit", "100");
  url.searchParams.set("order", "volume_24hr");
  url.searchParams.set("ascending", "false");
  url.searchParams.set("q", query);
  return url;
}

export function polymarketMarketsUrl(query: string) {
  const url = new URL("/markets", POLYMARKET_GAMMA_BASE_URL);
  url.searchParams.set("active", "true");
  url.searchParams.set("closed", "false");
  url.searchParams.set("limit", "100");
  url.searchParams.set("order", "volume_24hr");
  url.searchParams.set("ascending", "false");
  url.searchParams.set("q", query);
  return url;
}

function createTimedSignal(parentSignal?: AbortSignal, timeoutMs = POLYMARKET_GAMMA_FETCH_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(new Error(`Polymarket Gamma request timed out after ${timeoutMs}ms`)), timeoutMs);
  const abortFromParent = () => controller.abort(parentSignal?.reason);

  if (parentSignal) {
    setMaxListeners(0, parentSignal);
    if (parentSignal.aborted) {
      controller.abort(parentSignal.reason);
    } else {
      parentSignal.addEventListener("abort", abortFromParent, { once: true });
    }
  }

  return {
    signal: controller.signal,
    cleanup() {
      clearTimeout(timeoutId);
      if (parentSignal) parentSignal.removeEventListener("abort", abortFromParent);
    },
  };
}

async function fetchGammaEvents(query: string, signal?: AbortSignal): Promise<GammaEvent[]> {
  const url = polymarketEventsUrl(query);
  const timedSignal = createTimedSignal(signal);

  try {
    const response = await fetch(url, {
      signal: timedSignal.signal,
      cache: "no-store",
      headers: {
        accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Polymarket Gamma API returned ${response.status}`);
    }

    const data = (await response.json()) as unknown;
    return Array.isArray(data) ? (data as GammaEvent[]) : [];
  } finally {
    timedSignal.cleanup();
  }
}

async function fetchGammaMarkets(query: string, signal?: AbortSignal): Promise<GammaMarket[]> {
  const url = polymarketMarketsUrl(query);
  const timedSignal = createTimedSignal(signal);

  try {
    const response = await fetch(url, {
      signal: timedSignal.signal,
      cache: "no-store",
      headers: {
        accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Polymarket Gamma markets API returned ${response.status}`);
    }

    const data = (await response.json()) as unknown;
    return Array.isArray(data) ? (data as GammaMarket[]) : [];
  } finally {
    timedSignal.cleanup();
  }
}

function tagText(tags: GammaEvent["tags"]) {
  if (!Array.isArray(tags)) return "";
  return tags
    .map((tag) => {
      if (typeof tag === "string") return tag;
      return `${tag.label ?? ""} ${tag.name ?? ""} ${tag.slug ?? ""}`;
    })
    .join(" ");
}

function toUsefulNumber(...values: Array<number | string | undefined>) {
  for (const value of values) {
    const number = safeNumber(value);
    if (typeof number === "number" && Number.isFinite(number)) {
      return Math.max(0, Math.min(1, number));
    }
  }
  return undefined;
}

function alignOutcomePrices(market: GammaMarket, outcomeCount: number) {
  const explicitPrices = safeArray<unknown>(market.outcomePrices)
    .map((value) => safeNumber(value))
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
    .map((value) => Math.max(0, Math.min(1, value)));
  const fallbackPrice = toUsefulNumber(market.currentPrice, market.price, market.bestAsk, market.lastTradePrice, market.bestBid);
  const prices = explicitPrices.slice(0, Math.max(0, outcomeCount));

  if (!prices.length && typeof fallbackPrice === "number") {
    return outcomeCount >= 2 ? [fallbackPrice, Math.max(0, Math.min(1, 1 - fallbackPrice))] : [fallbackPrice];
  }

  if (prices.length === 1 && outcomeCount >= 2) {
    prices.push(Math.max(0, Math.min(1, 1 - prices[0])));
  }

  while (prices.length < outcomeCount && typeof fallbackPrice === "number") {
    prices.push(fallbackPrice);
  }

  return prices.slice(0, Math.max(1, outcomeCount));
}

function normalizeGammaMarket(market: GammaMarket, event?: GammaEvent): RawPolymarketMarket | undefined {
  const title = market.question ?? market.title ?? event?.title;
  if (!title) return undefined;

  const outcomes = safeArray<string>(market.outcomes).map(String);
  const outcomePrices = alignOutcomePrices(market, outcomes.length || 2);
  const assetIds = safeArray<string>(market.clobTokenIds).map(String);
  const eventTitle = event?.title ?? "";
  const combinedText = `${eventTitle} ${title} ${event?.category ?? ""} ${market.category ?? ""} ${tagText(event?.tags)} ${tagText(market.tags)}`;

  return {
    marketId: String(market.id ?? market.slug ?? market.conditionId ?? title),
    conditionId: market.conditionId,
    assetIds,
    title,
    slug: market.slug,
    category: market.category ?? event?.category,
    outcomes,
    outcomePrices,
    volume: safeNumber(market.volumeNum ?? market.volume ?? event?.volume),
    liquidity: safeNumber(market.liquidityNum ?? market.liquidity ?? event?.liquidity),
    active: market.active ?? event?.active,
    closed: market.closed ?? event?.closed,
    acceptingOrders: market.acceptingOrders,
    startDate: market.startDate ?? event?.startDate,
    endDate: market.endDate ?? event?.endDate,
    createdAt: market.createdAt ?? event?.createdAt,
    eventTitle,
    eventSlug: event?.slug,
    sport: detectSport(combinedText),
    sourceUrl: market.slug ? `https://polymarket.com/event/${market.slug}` : event?.slug ? `https://polymarket.com/event/${event.slug}` : undefined,
  };
}

const wrongSportOrNonSportsPatterns = [
  /\bnba\b/,
  /\bnhl\b/,
  /\bnfl\b/,
  /\bstanley cup\b/,
  /\bnba finals\b/,
  /\bsuper bowl\b/,
  /\bred wings\b/,
  /\bmaple leafs\b/,
  /\braptors\b/,
  /\blakers\b/,
  /\bclippers\b/,
  /\bhockey\b/,
  /\bbasketball\b/,
  /\bfootball\b/,
  /\bcrypto\b/,
  /\bbitcoin\b/,
  /\bethereum\b/,
  /\bstock\b/,
  /\bipo\b/,
  /\belection\b/,
  /\bpresident\b/,
];

const futuresPatterns = [
  /\bworld series\b/,
  /\bchampionship\b/,
  /\bchampion\b/,
  /\bdivision winner\b/,
  /\bwin (?:the )?division\b/,
  /\bmake (?:the )?playoffs\b/,
  /\bplayoff\b/,
  /\bmvp\b/,
  /\bcy young\b/,
  /\baward\b/,
  /\bseason wins?\b/,
  /\bpennant\b/,
];

function uniqueMlbTeamCount(text: string) {
  return new Set(mlbTeamHits(text).map((hit) => hit.profile.canonicalName)).size;
}

function orderedMlbTeams(text: string) {
  const normalized = normalizeText(text);
  const byTeam = new Map<string, { name: string; index: number }>();

  for (const hit of mlbTeamHits(text)) {
    const index = normalized.indexOf(hit.alias);
    const existing = byTeam.get(hit.profile.canonicalName);
    if (!existing || (index >= 0 && index < existing.index)) {
      byTeam.set(hit.profile.canonicalName, {
        name: hit.profile.canonicalName,
        index: index >= 0 ? index : Number.MAX_SAFE_INTEGER,
      });
    }
  }

  return Array.from(byTeam.values()).sort((a, b) => a.index - b.index).map((team) => team.name);
}

function hasMlbKeyword(text: string) {
  return /\bmlb\b|baseball|major league baseball/.test(normalizeText(text));
}

function nickname(team?: string) {
  const parts = (team ?? "").split(/\s+/).filter(Boolean);
  return parts.slice(-2).join(" ") || team || "";
}

export function mlbScheduleSearchTerms(games: AstroddsGameScan[] = []) {
  const terms = new Set(polymarketSportQueryTerms("MLB"));

  games.slice(0, 15).forEach((game) => {
    const away = game.awayTeam;
    const home = game.homeTeam;
    if (!away || !home) return;
    const awayNick = nickname(away);
    const homeNick = nickname(home);

    const awayProfile = findMlbTeamProfile(away);
    const homeProfile = findMlbTeamProfile(home);

    terms.add(`${away} ${home}`);
    terms.add(`${awayNick} ${homeNick}`);
    terms.add(`${away} ${home} MLB`);
    terms.add(`${awayNick} ${homeNick} baseball`);
    terms.add(`${awayProfile?.abbreviation ?? awayNick} ${homeProfile?.abbreviation ?? homeNick}`);
    terms.add(`${awayProfile?.abbreviation ?? awayNick} @ ${homeProfile?.abbreviation ?? homeNick}`);
    terms.add(`${awayNick} @ ${homeNick}`);
    terms.add(`${awayNick} vs ${homeNick}`);
    terms.add(`${away} MLB`);
    terms.add(`${home} MLB`);
    terms.add(`${awayNick} baseball`);
    terms.add(`${homeNick} baseball`);
    if (awayProfile) {
      terms.add(`${awayProfile.nickname} ${homeNick}`);
      terms.add(`${awayProfile.city} ${homeNick}`);
      terms.add(`${awayProfile.abbreviation} MLB`);
    }
    if (homeProfile) {
      terms.add(`${awayNick} ${homeProfile.nickname}`);
      terms.add(`${awayNick} ${homeProfile.city}`);
      terms.add(`${homeProfile.abbreviation} MLB`);
    }
  });

  return Array.from(terms).filter(Boolean).slice(0, 24);
}

function marketDisplayTitle(raw: Pick<RawPolymarketMarket, "eventTitle" | "title">) {
  return raw.eventTitle && raw.eventTitle !== raw.title ? `${raw.eventTitle} - ${raw.title}` : raw.title;
}

function rawMarketText(raw: RawPolymarketMarket) {
  return `${raw.eventTitle ?? ""} ${raw.title} ${raw.category ?? ""} ${raw.outcomes.join(" ")}`;
}

function hasSingleGameMlbMarketWording(text: string) {
  const normalized = normalizeText(text);
  return (
    /\bwill\b.*\bwin\b|\bwin\b.*\bon\b|\bgame winner\b|\bmoneyline\b|\bto win\b/.test(normalized) ||
    /\brun line\b|\bspread\b|[+-]\s*\d+(?:\.\d+)?/.test(text.toLowerCase()) ||
    /\bo\s*\/\s*u\b|\bover\s*\/\s*under\b|\bover\b|\bunder\b|\btotal runs\b|\btotal\b/.test(normalized) ||
    /\bscore\b|\bruns\b|\bstrikeouts\b|\btotal bases\b/.test(normalized)
  );
}

function rejectionReasonCounts(markets: RawPolymarketMarket[]) {
  const counts = new Map<string, number>();
  markets.forEach((market) => {
    const reason = market.rejectedReason ?? "Rejected by sport filter";
    counts.set(reason, (counts.get(reason) ?? 0) + 1);
  });
  return Array.from(counts.entries())
    .map(([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason));
}

function mlbRejectionReason(raw: RawPolymarketMarket) {
  const text = rawMarketText(raw);
  const normalized = text.toLowerCase();
  const normalizedStrict = normalizeText(text);
  const teamCount = uniqueMlbTeamCount(text);
  const betType = teamCount >= 2 && inferBetType(text) === "OTHER" ? "MONEYLINE" : inferBetType(text);
  const hasMlbContext = hasMlbKeyword(text) || teamCount > 0;
  const hasSingleGameWording = hasSingleGameMlbMarketWording(text);

  if (wrongSportOrNonSportsPatterns.some((pattern) => pattern.test(normalized)) && !hasMlbContext) {
    return "Rejected: wrong sport";
  }

  if (futuresPatterns.some((pattern) => pattern.test(normalized))) {
    return normalized.includes("world series") || normalized.includes("championship")
      ? "Rejected: season/championship market"
      : "Rejected: futures market";
  }

  if (teamCount === 0) return "Rejected: no MLB team alias";

  if (teamCount === 1 && !hasSingleGameWording && !/\bvs\b|\bat\b|\b@\b/.test(normalizedStrict)) {
    return "Rejected: no opponent match";
  }

  if (!["MONEYLINE", "SPREAD", "TOTAL", "PROP"].includes(betType)) {
    return "Rejected: unsupported market type";
  }

  return undefined;
}
export function getMlbMarketRejectionReason(title: string) {
  return mlbRejectionReason({
    marketId: title,
    assetIds: [],
    title,
    outcomes: [],
    outcomePrices: [],
  });
}

function filterPolymarketMarkets(rawMarkets: RawPolymarketMarket[], sport: AstroddsSportFilter) {
  const rejectedMarkets: RawPolymarketMarket[] = [];
  const acceptedRawMarkets = rawMarkets.filter((market) => {
    if (sport === "MLB") {
      const rejectedReason = mlbRejectionReason(market);
      if (!rejectedReason) return true;
      rejectedMarkets.push({ ...market, rejectedReason });
      return false;
    }

    if (sport === "ALL") return true;
    if (market.sport === sport) return true;
    rejectedMarkets.push({ ...market, rejectedReason: `Not ${sport} / no sport keyword match` });
    return false;
  });

  return { acceptedRawMarkets, rejectedMarkets };
}

export function rawToMarketScans(raw: RawPolymarketMarket): AstroddsMarketScan[] {
  const text = `${raw.eventTitle ?? ""} ${raw.title}`;
  const orderedTeams = orderedMlbTeams(text);
  const inferred = inferBetType(text);
  const betType = inferred === "OTHER" && orderedTeams.length >= 2 ? "MONEYLINE" : inferred;
  const status = inferMarketStatus(raw);
  const outcomes = raw.outcomes.length ? raw.outcomes : ["Yes", "No"];
  const prices = raw.outcomePrices;
  const totalLine = text.match(/(?:o\/u|over\/under|total|over|under)\s*([0-9]+(?:\.[0-9]+)?)/i)?.[1];
  const spreadLine = text.match(/([+-]\s*\d+(?:\.\d+)?)/)?.[1]?.replace(/\s+/g, "");
  const yesNoMarket = outcomes.every((outcome) => /^(yes|no)$/i.test(outcome.trim()));
  const totalIsUnder = /\bunder\b/i.test(text) && !/\bover\b/i.test(text);

  function mappedPick(outcome: string) {
    const normalizedOutcome = outcome.trim().toLowerCase();

    if (!yesNoMarket) {
      if (betType === "TOTAL" && /^(over|under)$/i.test(outcome.trim()) && totalLine) return `${outcome.trim()} ${totalLine}`;
      return outcome;
    }

    if (betType === "TOTAL" && totalLine) {
      if (normalizedOutcome === "yes") return `${totalIsUnder ? "Under" : "Over"} ${totalLine}`;
      return `${totalIsUnder ? "Over" : "Under"} ${totalLine}`;
    }

    if (betType === "MONEYLINE" && orderedTeams.length >= 1) {
      if (normalizedOutcome === "yes") return orderedTeams[0];
      if (orderedTeams.length >= 2) return orderedTeams[1];
    }

    if (betType === "SPREAD" && normalizedOutcome === "yes" && orderedTeams.length >= 1 && spreadLine) {
      return `${orderedTeams[0]} ${spreadLine}`;
    }

    return undefined;
  }

  return outcomes.flatMap((outcome, index) => {
    const pick = mappedPick(outcome);
    const price = prices[index];
    if (!pick) return [];
    if (typeof price !== "number" || !Number.isFinite(price)) return [];

    return [
      {
        marketId: raw.marketId,
        conditionId: raw.conditionId,
        assetId: raw.assetIds[index],
        marketTitle: raw.eventTitle && raw.eventTitle !== raw.title ? `${raw.eventTitle} - ${raw.title}` : raw.title,
        outcomes,
        betType,
        pick,
    currentPrice: Math.max(0, Math.min(1, price)),
    volume: raw.volume,
    liquidity: raw.liquidity,
    priceMovement: undefined,
    status,
    category: raw.category,
    sourceUrl: raw.sourceUrl,
    marketDate: raw.marketDate ?? raw.gameDate ?? raw.endDate ?? raw.startDate,
    gameDate: raw.gameDate ?? raw.marketDate ?? raw.startDate ?? raw.endDate,
    unmatchedReason: raw.rejectedReason,
    walletSupport: {
      status: "WALLET_LED",
      rank: "NONE",
      supportingWallets: 0,
          summary: "Wallet layer is separate; no tracked wallet confirmation attached to this market yet.",
        },
      },
    ];
  });
}

export function normalizePolymarketEvents(events: GammaEvent[], sport: AstroddsSportFilter) {
  const seen = new Set<string>();
  const rawMarkets: RawPolymarketMarket[] = [];

  events.forEach((event) => {
    event.markets?.forEach((market) => {
      const normalized = normalizeGammaMarket(market, event);
      if (!normalized) return;
      const key = `${normalized.marketId}-${normalized.conditionId ?? ""}-${normalized.title}`;
      if (seen.has(key)) return;
      seen.add(key);
      rawMarkets.push(normalized);
    });
  });

  const { acceptedRawMarkets, rejectedMarkets } = filterPolymarketMarkets(rawMarkets, sport);

  const markets = acceptedRawMarkets.flatMap(rawToMarketScans);
  const unclearYesNoRejected = acceptedRawMarkets.filter((market) => {
    const outcomes = market.outcomes.length ? market.outcomes : ["Yes", "No"];
    return outcomes.every((outcome) => /^(yes|no)$/i.test(outcome.trim())) && rawToMarketScans(market).length === 0;
  }).length;

  return {
    rawEventsFetched: events.length,
    rawMarketsFetched: rawMarkets.length,
    acceptedRawMarkets,
    rejectedMarkets,
    markets,
    unclearYesNoRejected,
    rawMarketSamples: rawMarkets.slice(0, 10).map(marketDisplayTitle),
    mlbCandidateMarketSamples: acceptedRawMarkets.slice(0, 10).map(marketDisplayTitle),
    rejectionReasonCounts: rejectionReasonCounts(rejectedMarkets).slice(0, 10),
  };
}

export function normalizePolymarketSources(events: GammaEvent[], directMarkets: GammaMarket[], sport: AstroddsSportFilter) {
  const directEvents: GammaEvent[] = directMarkets.map((market) => ({
    title: market.question ?? market.title,
    slug: market.slug,
    category: market.category,
    active: market.active,
    closed: market.closed,
    startDate: market.startDate,
    endDate: market.endDate,
    createdAt: market.createdAt,
    markets: [market],
  }));

  return normalizePolymarketEvents([...events, ...directEvents], sport);
}

export async function fetchPolymarketSportsMarkets(
  sport: AstroddsSportFilter,
  signal?: AbortSignal,
  games: AstroddsGameScan[] = [],
): Promise<{
  markets: AstroddsMarketScan[];
  rawMarkets: RawPolymarketMarket[];
  status: "CONNECTED" | "PARTIAL";
  diagnostics: AstroddsScanDiagnostics["polymarket"];
  orderBookDiagnostics: AstroddsScanDiagnostics["orderBook"];
}> {
  const terms = sport === "MLB" ? mlbScheduleSearchTerms(games) : polymarketSportQueryTerms(sport);
  const queryStrategiesUsed =
    sport === "MLB"
      ? ["sport keyword", "schedule team pair", "team + MLB/baseball context", "Gamma events endpoint", "Gamma markets endpoint"]
      : ["sport keyword", "Gamma events endpoint"];
  const teamSearchQueriesAttempted = sport === "MLB" ? terms.filter((term) => !polymarketSportQueryTerms("MLB").includes(term)) : [];
  const sourceUrl = terms
    .flatMap((term) => [polymarketEventsUrl(term).toString(), polymarketMarketsUrl(term).toString()])
    .join(" | ");
  const events: GammaEvent[] = [];
  const directMarkets: GammaMarket[] = [];
  const errors: string[] = [];
  const batchSize = sport === "MLB" ? 8 : 12;

  for (let index = 0; index < terms.length; index += batchSize) {
    const batch = terms.slice(index, index + batchSize);
    const [batchEvents, batchMarkets] = await Promise.all([
      Promise.allSettled(batch.map((term) => fetchGammaEvents(term, signal))),
      Promise.allSettled(batch.map((term) => fetchGammaMarkets(term, signal))),
    ]);
    events.push(
      ...batchEvents.flatMap((result) => {
        if (result.status === "fulfilled") return result.value;
        errors.push(result.reason instanceof Error ? result.reason.message : "Unknown Polymarket query failure");
        return [];
      }),
    );
    directMarkets.push(
      ...batchMarkets.flatMap((result) => {
        if (result.status === "fulfilled") return result.value;
        errors.push(result.reason instanceof Error ? result.reason.message : "Unknown Polymarket markets query failure");
        return [];
      }),
    );
  }
  const normalized = normalizePolymarketSources(events, directMarkets, sport);
  const hydrated = await hydrateMarketsWithOrderBooks(normalized.markets, signal, "SERVER");
  const hadErrors = errors.length > 0;
  const diagnosticStatus: AstroddsDiagnosticStatus =
    !events.length && !directMarkets.length
      ? "FAILED"
      : hadErrors || (sport === "MLB" && normalized.acceptedRawMarkets.length === 0)
        ? "PARTIAL"
        : "CONNECTED_SERVER";

  return {
    rawMarkets: normalized.acceptedRawMarkets,
    markets: hydrated.markets,
    status: !events.length && !directMarkets.length || hadErrors || normalized.acceptedRawMarkets.length === 0 ? "PARTIAL" : "CONNECTED",
    diagnostics: {
      status: diagnosticStatus,
      sourceMode: diagnosticStatus === "FAILED" ? "FAILED" : "SERVER",
      marketsFetched: normalized.rawMarketsFetched,
      sportsMarketsDetected: normalized.acceptedRawMarkets.length,
      marketsMatchedToGames: 0,
      rawEventsFetched: normalized.rawEventsFetched,
      rawMarketsFetched: normalized.rawMarketsFetched,
      rejectedNonMlbMarkets: sport === "MLB" ? normalized.rejectedMarkets.length : undefined,
      mlbMarketsDetected: sport === "MLB" ? normalized.acceptedRawMarkets.length : undefined,
      singleGameMlbMarketsDetected: sport === "MLB" ? normalized.markets.length : undefined,
      queryStrategiesUsed,
      teamSearchQueriesAttempted: teamSearchQueriesAttempted.slice(0, 40),
      futuresRejected: sport === "MLB" ? normalized.rejectedMarkets.filter((market) => market.rejectedReason?.includes("futures") || market.rejectedReason?.includes("season/championship")).length : undefined,
      wrongSportsRejected: sport === "MLB" ? normalized.rejectedMarkets.filter((market) => market.rejectedReason?.includes("wrong sport")).length : undefined,
      noMlbTeamMatchRejected: sport === "MLB" ? normalized.rejectedMarkets.filter((market) => market.rejectedReason?.includes("no MLB team alias") || market.rejectedReason?.includes("no opponent match") || market.rejectedReason?.includes("no MLB game match") || market.rejectedReason?.includes("unrelated prediction")).length : undefined,
      unclearYesNoRejected: sport === "MLB" ? normalized.unclearYesNoRejected : undefined,
      rejectedMarkets: normalized.rejectedMarkets.slice(0, 20).map((market) => ({
        title: market.eventTitle && market.eventTitle !== market.title ? `${market.eventTitle} - ${market.title}` : market.title,
        rejectedReason: market.rejectedReason ?? "Rejected by sport filter",
      })),
      rawMarketSamples: normalized.rawMarketSamples,
      mlbCandidateMarketSamples: normalized.mlbCandidateMarketSamples,
      rejectionReasonCounts: normalized.rejectionReasonCounts,
      error:
        errors.length || (sport === "MLB" && normalized.acceptedRawMarkets.length === 0)
          ? [errors.join(" | "), sport === "MLB" && normalized.acceptedRawMarkets.length === 0 ? "Polymarket connected, but no active single-game MLB markets were detected after team-alias filtering." : ""]
              .filter(Boolean)
              .join(" ")
          : undefined,
      sourceUrl,
    },
    orderBookDiagnostics: hydrated.diagnostics,
  };
}
