import { normalizeText, safeNumber } from "./normalize";

export type AstroddsOddsConnectionStatus = "CONNECTED" | "PARTIAL" | "NOT_CONNECTED" | "FAILED";

export type AstroddsNormalizedOdd = {
  provider: string;
  sport: string;
  gameId?: string;
  game: string;
  homeTeam: string;
  awayTeam: string;
  marketType: "moneyline" | "spread" | "total" | "unknown";
  marketLabel: string;
  side: string;
  line?: number;
  priceAmerican?: number;
  priceDecimal?: number;
  impliedProbability?: number;
  lastUpdated?: string;
  sourceUrl?: string;
};

export type AstroddsOddsLayerStatus = {
  status: AstroddsOddsConnectionStatus;
  provider: string;
  sourceUrl?: string;
  keyConfigured: boolean;
  supportedMarkets: string[];
  priceAvailable: boolean;
  officialBetEligibility: boolean;
  reason: string;
};

export type AstroddsOddsFetchResult = AstroddsOddsLayerStatus & {
  odds: AstroddsNormalizedOdd[];
  error?: string;
};

const SUPPORTED_MARKETS = ["Moneyline / Winner", "Spread / Handicap", "Totals / Over-Under"];

function envValue(name: string) {
  const value = process.env[name];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function defaultBaseUrl(provider: string) {
  if (provider.toLowerCase().includes("oddsapi") || provider.toLowerCase().includes("the-odds-api")) {
    return "https://api.the-odds-api.com/v4";
  }
  return envValue("ODDS_API_BASE_URL");
}

export function getOddsLayerStatus(): AstroddsOddsLayerStatus {
  const provider = envValue("ODDS_API_PROVIDER") ?? "NOT_CONFIGURED";
  const keyConfigured = Boolean(envValue("ODDS_API_KEY"));
  const baseUrl = defaultBaseUrl(provider);

  if (!keyConfigured || !baseUrl) {
    return {
      status: "NOT_CONNECTED",
      provider,
      sourceUrl: baseUrl,
      keyConfigured,
      supportedMarkets: SUPPORTED_MARKETS,
      priceAvailable: false,
      officialBetEligibility: false,
      reason: "Odds source not connected - official sports paper picks blocked.",
    };
  }

  return {
    status: "PARTIAL",
    provider,
    sourceUrl: baseUrl,
    keyConfigured,
    supportedMarkets: SUPPORTED_MARKETS,
    priceAvailable: false,
    officialBetEligibility: false,
    reason: "Odds provider configured. Fetch adapters are enabled only for supported real market responses.",
  };
}

function americanToDecimal(price?: number) {
  if (typeof price !== "number" || !Number.isFinite(price) || price === 0) return undefined;
  return price > 0 ? 1 + price / 100 : 1 + 100 / Math.abs(price);
}

function decimalToImplied(decimal?: number) {
  if (typeof decimal !== "number" || !Number.isFinite(decimal) || decimal <= 1) return undefined;
  return 1 / decimal;
}

function marketTypeFromKey(key?: string): AstroddsNormalizedOdd["marketType"] {
  const text = normalizeText(key);
  if (text.includes("h2h") || text.includes("moneyline") || text.includes("winner")) return "moneyline";
  if (text.includes("spread") || text.includes("handicap")) return "spread";
  if (text.includes("total") || text.includes("over under")) return "total";
  return "unknown";
}

function marketLabel(type: AstroddsNormalizedOdd["marketType"], rawKey?: string) {
  const raw = normalizeText(rawKey);
  if (type === "moneyline") return raw.includes("winner") ? "Winner" : "Moneyline / Winner";
  if (type === "spread") return raw.includes("run line") ? "Run Line" : raw.includes("puck line") ? "Puck Line" : "Spread / Handicap";
  if (type === "total") return "Totals / Over-Under";
  return "Unknown";
}

type OddsApiOutcome = {
  name?: string;
  price?: number;
  point?: number;
};

type OddsApiMarket = {
  key?: string;
  last_update?: string;
  outcomes?: OddsApiOutcome[];
};

type OddsApiBookmaker = {
  key?: string;
  title?: string;
  last_update?: string;
  markets?: OddsApiMarket[];
};

type OddsApiEvent = {
  id?: string;
  sport_key?: string;
  home_team?: string;
  away_team?: string;
  commence_time?: string;
  bookmakers?: OddsApiBookmaker[];
};

function normalizeTheOddsApiEvent(event: OddsApiEvent, sourceUrl: string, provider: string): AstroddsNormalizedOdd[] {
  const homeTeam = event.home_team;
  const awayTeam = event.away_team;
  if (!homeTeam || !awayTeam) return [];
  const bookmaker = event.bookmakers?.[0];
  if (!bookmaker) return [];

  return (bookmaker.markets ?? []).flatMap((market) => {
    const type = marketTypeFromKey(market.key);
    if (type === "unknown") return [];
    return (market.outcomes ?? []).flatMap((outcome) => {
      const decimal = americanToDecimal(outcome.price);
      const implied = decimalToImplied(decimal);
      const side = outcome.name;
      if (!side || typeof outcome.price !== "number" || !decimal || !implied) return [];
      return [{
        provider,
        sport: event.sport_key ?? "UNKNOWN",
        gameId: event.id,
        game: `${awayTeam} vs ${homeTeam}`,
        homeTeam,
        awayTeam,
        marketType: type,
        marketLabel: marketLabel(type, market.key),
        side,
        line: safeNumber(outcome.point),
        priceAmerican: outcome.price,
        priceDecimal: decimal,
        impliedProbability: implied,
        lastUpdated: market.last_update ?? bookmaker.last_update ?? event.commence_time,
        sourceUrl,
      } satisfies AstroddsNormalizedOdd];
    });
  });
}

export async function fetchConfiguredSportsOdds(sportKey = "baseball_mlb", signal?: AbortSignal): Promise<AstroddsOddsFetchResult> {
  const status = getOddsLayerStatus();
  if (!status.keyConfigured || !status.sourceUrl) return { ...status, odds: [] };

  const provider = status.provider;
  const base = status.sourceUrl.replace(/\/$/, "");
  const url = new URL(`${base}/sports/${sportKey}/odds`);
  url.searchParams.set("apiKey", envValue("ODDS_API_KEY") ?? "");
  url.searchParams.set("regions", envValue("ODDS_API_REGIONS") ?? "us");
  url.searchParams.set("markets", envValue("ODDS_API_MARKETS") ?? "h2h,spreads,totals");
  url.searchParams.set("oddsFormat", "american");

  try {
    const response = await fetch(url, { signal, headers: { accept: "application/json" }, next: { revalidate: 120 } });
    if (!response.ok) throw new Error(`Odds provider returned ${response.status}`);
    const payload = (await response.json()) as unknown;
    const events = Array.isArray(payload) ? payload as OddsApiEvent[] : [];
    const odds = events.flatMap((event) => normalizeTheOddsApiEvent(event, url.toString().replace(envValue("ODDS_API_KEY") ?? "", "***"), provider));
    return {
      ...status,
      status: odds.length ? "CONNECTED" : "PARTIAL",
      priceAvailable: odds.length > 0,
      officialBetEligibility: odds.length > 0,
      reason: odds.length ? "Real odds source connected with supported markets." : "Odds source connected but no supported markets returned.",
      sourceUrl: url.toString().replace(envValue("ODDS_API_KEY") ?? "", "***"),
      odds,
    };
  } catch (error) {
    return {
      ...status,
      status: "FAILED",
      priceAvailable: false,
      officialBetEligibility: false,
      reason: "Odds source failed - official sports paper picks blocked.",
      sourceUrl: url.toString().replace(envValue("ODDS_API_KEY") ?? "", "***"),
      odds: [],
      error: error instanceof Error ? error.message : "Unknown odds provider failure.",
    };
  }
}