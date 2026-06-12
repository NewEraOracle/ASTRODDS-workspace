import { normalizeText } from "./normalize";

export type MlbTeamProfile = {
  canonicalName: string;
  city: string;
  nickname: string;
  abbreviation: string;
  aliases: string[];
};

type AliasHit = {
  profile: MlbTeamProfile;
  alias: string;
  strength: number;
  ambiguous: boolean;
};

export type MlbGameMarketMatch = {
  matched: boolean;
  score: number;
  reason: string;
  unmatchedReason: string;
};

export const MLB_TEAMS: MlbTeamProfile[] = [
  team("Arizona Diamondbacks", "Arizona", "Diamondbacks", "ARI", ["D-backs", "Dbacks", "D backs", "Arizona D-backs", "AZ Diamondbacks", "AZ D-backs", "ARZ"]),
  team("Atlanta Braves", "Atlanta", "Braves", "ATL", ["Atl Braves"]),
  team("Baltimore Orioles", "Baltimore", "Orioles", "BAL", ["Bal Orioles", "Os"]),
  team("Boston Red Sox", "Boston", "Red Sox", "BOS", ["Boston Sox", "Bosox", "BoSox", "Sox"]),
  team("Chicago Cubs", "Chicago", "Cubs", "CHC", ["Chi Cubs", "CH Cubs"]),
  team("Chicago White Sox", "Chicago", "White Sox", "CWS", ["Chi Sox", "WhiteSox", "Chicago Sox", "CHW", "Sox"]),
  team("Cincinnati Reds", "Cincinnati", "Reds", "CIN", ["Cincy Reds", "Cin Reds"]),
  team("Cleveland Guardians", "Cleveland", "Guardians", "CLE", ["Cle Guardians"]),
  team("Colorado Rockies", "Colorado", "Rockies", "COL", ["Col Rockies"]),
  team("Detroit Tigers", "Detroit", "Tigers", "DET", ["Det Tigers"]),
  team("Houston Astros", "Houston", "Astros", "HOU", ["Hou Astros"]),
  team("Kansas City Royals", "Kansas City", "Royals", "KC", ["KCR", "KC Royals"]),
  team("Los Angeles Angels", "Los Angeles", "Angels", "LAA", ["LA Angels", "L.A. Angels", "Anaheim Angels", "Anaheim", "Los Angeles Angels of Anaheim"]),
  team("Los Angeles Dodgers", "Los Angeles", "Dodgers", "LAD", ["LA Dodgers", "L.A. Dodgers"]),
  team("Miami Marlins", "Miami", "Marlins", "MIA", ["Mia Marlins"]),
  team("Milwaukee Brewers", "Milwaukee", "Brewers", "MIL", ["Mil Brewers"]),
  team("Minnesota Twins", "Minnesota", "Twins", "MIN", ["Minn Twins"]),
  team("New York Mets", "New York", "Mets", "NYM", ["NY Mets", "N.Y. Mets"]),
  team("New York Yankees", "New York", "Yankees", "NYY", ["NY Yankees", "N.Y. Yankees", "Yanks"]),
  team("Athletics", "Sacramento", "Athletics", "ATH", ["A's", "The Athletics", "Sacramento Athletics", "Oakland Athletics", "Oakland A's", "Oakland", "OAK"]),
  team("Philadelphia Phillies", "Philadelphia", "Phillies", "PHI", ["Philly", "Phils", "Phi Phillies"]),
  team("Pittsburgh Pirates", "Pittsburgh", "Pirates", "PIT", ["Pitt Pirates"]),
  team("San Diego Padres", "San Diego", "Padres", "SD", ["SDP", "SD Padres"]),
  team("San Francisco Giants", "San Francisco", "Giants", "SF", ["SFG", "SF Giants"]),
  team("Seattle Mariners", "Seattle", "Mariners", "SEA", ["Sea Mariners"]),
  team("St. Louis Cardinals", "St. Louis", "Cardinals", "STL", ["Saint Louis Cardinals", "St Louis Cardinals", "St Louis", "Saint Louis", "STL Cardinals"]),
  team("Tampa Bay Rays", "Tampa Bay", "Rays", "TB", ["TBR", "TB Rays", "Tampa Rays"]),
  team("Texas Rangers", "Texas", "Rangers", "TEX", ["Tex Rangers"]),
  team("Toronto Blue Jays", "Toronto", "Blue Jays", "TOR", ["Jays", "Bluejays", "Tor Blue Jays"]),
  team("Washington Nationals", "Washington", "Nationals", "WSH", ["WSN", "Nats", "Wash Nationals"]),
];

const aliasCounts = new Map<string, number>();

MLB_TEAMS.forEach((profile) => {
  new Set(profile.aliases.map(normalizeText).filter(Boolean)).forEach((alias) => {
    aliasCounts.set(alias, (aliasCounts.get(alias) ?? 0) + 1);
  });
});

function team(canonicalName: string, city: string, nickname: string, abbreviation: string, extraAliases: string[] = []): MlbTeamProfile {
  const aliases = [canonicalName, `${city} ${nickname}`, nickname, city, abbreviation, ...extraAliases];
  return {
    canonicalName,
    city,
    nickname,
    abbreviation,
    aliases: Array.from(new Set(aliases.map(normalizeText).filter(Boolean))),
  };
}

function containsAlias(normalizedText: string, alias: string) {
  if (!alias) return false;
  return new RegExp(`(^|\\s)${escapeRegExp(alias)}(\\s|$)`).test(normalizedText);
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function aliasStrength(profile: MlbTeamProfile, alias: string) {
  if (alias === normalizeText(profile.canonicalName) || alias === normalizeText(`${profile.city} ${profile.nickname}`)) return 5;
  if (alias === normalizeText(profile.nickname)) return 4;
  if (alias === normalizeText(profile.abbreviation)) return 3;
  if (alias === normalizeText(profile.city)) return 2;
  return alias.length > 3 ? 3 : 2;
}

export function findMlbTeamProfile(teamName?: string) {
  const normalizedTeam = normalizeText(teamName);
  if (!normalizedTeam) return undefined;

  const exact = MLB_TEAMS.find((profile) =>
    profile.aliases.some((alias) => normalizedTeam === alias || normalizedTeam === normalizeText(profile.canonicalName)),
  );
  if (exact) return exact;

  const candidates = MLB_TEAMS.flatMap((profile) => {
    const aliases = profile.aliases.filter((alias) => normalizedTeam.includes(alias) || alias.includes(normalizedTeam));
    return aliases.map((alias) => ({
      profile,
      alias,
      strength: aliasStrength(profile, alias),
    }));
  }).sort((a, b) => b.strength - a.strength || b.alias.length - a.alias.length);

  return candidates[0]?.profile;
}

export function mlbTeamHits(text: string): AliasHit[] {
  const normalizedText = normalizeText(text);
  if (!normalizedText) return [];

  const hits = MLB_TEAMS.flatMap((profile) => {
    const hits = profile.aliases
      .filter((alias) => containsAlias(normalizedText, alias))
      .map((alias) => ({
        profile,
        alias,
        strength: aliasStrength(profile, alias),
        ambiguous: (aliasCounts.get(alias) ?? 0) > 1,
      }))
      .sort((a, b) => b.strength - a.strength || b.alias.length - a.alias.length);

    return hits[0] ? [hits[0]] : [];
  });

  return hits.filter(
    (hit) =>
      !(hit.ambiguous && hit.strength <= 2 && hits.some((other) => other !== hit && other.strength >= 4 && other.alias.includes(hit.alias))),
  );
}

export function describeMlbMarketTeams(text: string) {
  const hits = mlbTeamHits(text);
  return hits.map((hit) => `${hit.profile.canonicalName} via "${hit.alias}"`);
}

function hasMlbKeyword(text: string) {
  return /\bmlb\b|baseball|major league baseball/i.test(text);
}

function hasDateLikeContext(text: string) {
  return /\b\d{4}-\d{2}-\d{2}\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}\b|\b\d{1,2}\/(?:\d{1,2})\b/i.test(text);
}

function hasSingleGameWinContext(text: string) {
  const normalized = normalizeText(text);
  return /\bwill\b.*\bwin\b|\bwin\b.*\bon\b|\bgame winner\b|\bmoneyline\b|\bto win\b/.test(normalized);
}

export function matchMlbMarketToGame(input: {
  awayTeam?: string;
  homeTeam?: string;
  game: string;
  gameDate?: string;
  marketTitle: string;
  marketPick: string;
  marketOutcomes?: string[];
  betType?: string;
  marketDate?: string;
}): MlbGameMarketMatch {
  const away = findMlbTeamProfile(input.awayTeam);
  const home = findMlbTeamProfile(input.homeTeam);
  const marketText = `${input.marketTitle} ${input.marketPick} ${(input.marketOutcomes ?? []).join(" ")}`;
  const normalizedMarketText = normalizeText(marketText);
  const hits = mlbTeamHits(marketText);
  const gameDate = dateOnly(input.gameDate);
  const marketDate = dateOnly(input.marketDate);

  if (!away || !home) {
    return {
      matched: false,
      score: 0,
      reason: "",
      unmatchedReason: "MLB schedule row is missing a recognized home or away team alias.",
    };
  }

  const awayHit = hits.find((hit) => hit.profile.canonicalName === away.canonicalName);
  const homeHit = hits.find((hit) => hit.profile.canonicalName === home.canonicalName);
  const oppositeHits = hits.filter(
    (hit) => hit.profile.canonicalName !== away.canonicalName && hit.profile.canonicalName !== home.canonicalName,
  );
  const hitNames = hits.map((hit) => hit.profile.canonicalName).join(", ");

  if (oppositeHits.length) {
    return {
      matched: false,
      score: 0.1,
      reason: "",
      unmatchedReason: `Market mentions other MLB team aliases (${oppositeHits.map((hit) => hit.profile.canonicalName).join(", ")}), not this game.`,
    };
  }

  if (awayHit && homeHit) {
    if (gameDate && marketDate && gameDate !== marketDate) {
      return {
        matched: false,
        score: 0.12,
        reason: "",
        unmatchedReason: `Market date ${marketDate} does not match MLB game date ${gameDate}.`,
      };
    }

    return {
      matched: true,
      score: 1,
      reason: `Matched both MLB teams: ${away.canonicalName} via "${awayHit.alias}" and ${home.canonicalName} via "${homeHit.alias}".`,
      unmatchedReason: "",
    };
  }

  const singleHit = awayHit ?? homeHit;
  const hasBaseballContext = hasMlbKeyword(marketText);
  const hasOpponentContext =
    Boolean(awayHit && normalizedMarketText.includes(normalizeText(home.nickname))) ||
    Boolean(homeHit && normalizedMarketText.includes(normalizeText(away.nickname))) ||
    Boolean(awayHit && normalizedMarketText.includes(normalizeText(home.canonicalName))) ||
    Boolean(homeHit && normalizedMarketText.includes(normalizeText(away.canonicalName)));

  if (singleHit && input.betType === "MONEYLINE" && (hasBaseballContext || hasDateLikeContext(input.marketTitle) || hasSingleGameWinContext(input.marketTitle))) {
    if (gameDate && marketDate && gameDate !== marketDate) {
      return {
        matched: false,
        score: 0.18,
        reason: "",
        unmatchedReason: `Market date ${marketDate} does not match MLB game date ${gameDate}.`,
      };
    }

    return {
      matched: true,
      score: hasDateLikeContext(input.marketTitle) ? 0.78 : 0.66,
      reason: `Matched one-team MLB moneyline ${singleHit.profile.canonicalName} via "${singleHit.alias}" with single-game win/date context.`,
      unmatchedReason: "",
    };
  }

  if (singleHit && input.betType !== "SPREAD") {
    return {
      matched: false,
      score: 0.48,
      reason: "",
      unmatchedReason: `Only one MLB team (${singleHit.profile.canonicalName}) matched. Normal MLB game markets need both teams unless this is a clearly dated moneyline or run line.`,
    };
  }

  if (singleHit && input.betType === "SPREAD" && (hasBaseballContext || hasOpponentContext || hasDateLikeContext(input.marketTitle) || singleHit.strength >= 4)) {
    if (gameDate && marketDate && gameDate !== marketDate) {
      return {
        matched: false,
        score: 0.18,
        reason: "",
        unmatchedReason: `Market date ${marketDate} does not match MLB game date ${gameDate}.`,
      };
    }

    return {
      matched: true,
      score: 0.72,
      reason: `Matched single MLB team alias ${singleHit.profile.canonicalName} via "${singleHit.alias}" for a run line market with strong MLB team context.`,
      unmatchedReason: "",
    };
  }

  if (singleHit && input.betType === "SPREAD") {
    return {
      matched: false,
      score: 0.42,
      reason: "",
      unmatchedReason: `Only ${singleHit.profile.canonicalName} matched. One-team run line markets need MLB/baseball context, a date, or the opponent in the market title.`,
    };
  }

  if (singleHit?.ambiguous) {
    return {
      matched: false,
      score: 0.34,
      reason: "",
      unmatchedReason: `Only ambiguous city alias "${singleHit.alias}" matched; market needs a nickname, abbreviation, or opponent.`,
    };
  }

  if (hits.length) {
    return {
      matched: false,
      score: 0.22,
      reason: "",
      unmatchedReason: `Detected MLB aliases (${hitNames}), but none belong to ${input.game}.`,
    };
  }

  return {
    matched: false,
    score: 0,
    reason: "",
    unmatchedReason: "No MLB team alias found in market title, pick, or outcomes.",
  };
}

function dateOnly(value?: string) {
  if (!value) return undefined;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return undefined;
  return parsed.toISOString().slice(0, 10);
}
