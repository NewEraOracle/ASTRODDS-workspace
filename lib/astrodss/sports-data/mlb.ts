import type {
  AstroddsGameScan,
  AstroddsMlbGameContext,
  AstroddsMlbModelPick,
  AstroddsMlbPitcherContext,
  AstroddsMlbTeamRecord,
  AstroddsScanDiagnostics,
  AstroddsSourceDiagnostic,
  AstroddsSourceStatus,
  AstroddsWeatherContext,
} from "./types";
import { addDaysIsoDate, dataStatusRank, safeNumber, todayIsoDate } from "./normalize";
import { fetchWeatherContext, OPEN_METEO_FORECAST_URL } from "./weather";
import { findVenueCoordinates } from "./venues";

export const MLB_STATS_API_BASE = "https://statsapi.mlb.com/api/v1";
export const MLB_SOURCE_URL_BASE = `${MLB_STATS_API_BASE}/schedule`;

const MLB_SPORT_ID = "1";

type MlbScheduleResponse = {
  dates?: Array<{
    games?: MlbGame[];
  }>;
};

type MlbGame = {
  gamePk: number;
  gameDate?: string;
  status?: {
    abstractGameState?: string;
    detailedState?: string;
    codedGameState?: string;
  };
  teams?: {
    away?: MlbGameTeam;
    home?: MlbGameTeam;
  };
  venue?: {
    name?: string;
    location?: {
      defaultCoordinates?: {
        latitude?: number;
        longitude?: number;
      };
      latitude?: number;
      longitude?: number;
    };
  };
  linescore?: {
    currentInningOrdinal?: string;
    inningState?: string;
  };
};

type MlbGameTeam = {
  team?: { id?: number; name?: string };
  probablePitcher?: MlbPitcherRef;
  score?: number;
};

type MlbPitcherRef = {
  id?: number;
  fullName?: string;
  pitchHand?: { code?: string; description?: string };
};

type MlbStandingsResponse = {
  records?: Array<{
    teamRecords?: Array<{
      team?: { id?: number; name?: string };
      leagueRecord?: { wins?: number; losses?: number; pct?: string };
      streak?: { streakCode?: string; streakType?: string; streakNumber?: number };
    }>;
  }>;
};

type MlbPeopleResponse = {
  people?: MlbPerson[];
};

type MlbPerson = {
  id?: number;
  fullName?: string;
  pitchHand?: { code?: string; description?: string };
  stats?: Array<{
    splits?: Array<{
      stat?: {
        era?: string;
        whip?: string;
        strikeOuts?: number | string;
        wins?: number | string;
        losses?: number | string;
      };
    }>;
  }>;
};

type RecentTeamForm = {
  teamId: number;
  teamName: string;
  games: number;
  wins: number;
  losses: number;
  runsFor: number;
  runsAgainst: number;
};

type MlbGameWithWeather = AstroddsGameScan & {
  venueMapped: boolean;
};

export function mlbScheduleUrl(daysAhead = 4) {
  const url = new URL(MLB_SOURCE_URL_BASE);
  url.searchParams.set("sportId", MLB_SPORT_ID);
  url.searchParams.set("startDate", todayIsoDate());
  url.searchParams.set("endDate", addDaysIsoDate(daysAhead));
  url.searchParams.set("hydrate", "probablePitcher(note),venue,linescore");
  return url;
}

export function mlbRecentResultsUrl(daysBack = 14) {
  const url = new URL(MLB_SOURCE_URL_BASE);
  url.searchParams.set("sportId", MLB_SPORT_ID);
  url.searchParams.set("startDate", addDaysIsoDate(-daysBack));
  url.searchParams.set("endDate", addDaysIsoDate(-1));
  url.searchParams.set("hydrate", "linescore");
  return url;
}

export function mlbStandingsUrl() {
  const url = new URL(`${MLB_STATS_API_BASE}/standings`);
  url.searchParams.set("leagueId", "103,104");
  url.searchParams.set("season", todayIsoDate().slice(0, 4));
  return url;
}

function mlbPeopleUrl(ids: number[]) {
  const url = new URL(`${MLB_STATS_API_BASE}/people`);
  url.searchParams.set("personIds", ids.join(","));
  url.searchParams.set("hydrate", "stats(group=[pitching],type=[season])");
  return url;
}

function sanitizedSourceUrl(url: URL) {
  return `${url.origin}${url.pathname}`;
}

function sourceErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "unknown error";
}

async function fetchJson<T>(
  url: URL,
  signal: AbortSignal | undefined,
  sourceDiagnostics: AstroddsSourceDiagnostic[],
  endpointLabel: string,
  timeoutMs = 12_000,
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const abortFromParent = () => controller.abort();
  signal?.addEventListener("abort", abortFromParent, { once: true });
  const diagnosticBase = {
    sourceLabel: "MLB StatsAPI",
    endpointLabel,
    timedOut: false,
    sanitizedUrl: sanitizedSourceUrl(url),
    retryCount: 0,
  };

  try {
    const response = await fetch(url, {
      signal: controller.signal,
      next: { revalidate: 300 },
      headers: { accept: "application/json" },
    });

    if (!response.ok) {
      sourceDiagnostics.push({
        ...diagnosticBase,
        status: "FAILED",
        httpStatus: response.status,
        timedOut,
        errorMessage: `${endpointLabel} returned HTTP ${response.status}`,
      });
      throw new Error(`${endpointLabel} returned ${response.status}`);
    }

    sourceDiagnostics.push({
      ...diagnosticBase,
      status: "OK",
      httpStatus: response.status,
      timedOut: false,
    });
    return (await response.json()) as T;
  } catch (error) {
    const errorMessage = timedOut ? `${endpointLabel} timed out after ${timeoutMs}ms` : sourceErrorMessage(error);
    if (!sourceDiagnostics.some((item) => item.endpointLabel === endpointLabel && item.status === "FAILED")) {
      sourceDiagnostics.push({
        ...diagnosticBase,
        status: "FAILED",
        timedOut,
        errorMessage,
      });
    }
    throw new Error(errorMessage);
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", abortFromParent);
  }
}

function liveStatus(game: MlbGame) {
  const state = `${game.status?.abstractGameState ?? ""} ${game.status?.detailedState ?? ""}`.toLowerCase();
  if (state.includes("final")) return "FINAL" as const;
  if (state.includes("live") || state.includes("in progress")) return "LIVE" as const;
  if (state.includes("preview") || state.includes("scheduled") || state.includes("pre-game")) return "PRE_GAME" as const;
  return "UNKNOWN" as const;
}

function score(game: MlbGame) {
  const away = game.teams?.away?.score;
  const home = game.teams?.home?.score;
  if (typeof away === "number" && typeof home === "number") return `${away}-${home}`;
  return "0-0";
}

function hasProbablePitcher(game: MlbGame) {
  return Boolean(game.teams?.away?.probablePitcher?.fullName || game.teams?.home?.probablePitcher?.fullName);
}

function hasBothProbablePitchers(game: MlbGame) {
  return Boolean(game.teams?.away?.probablePitcher?.fullName && game.teams?.home?.probablePitcher?.fullName);
}

function stripVenueMapped(game: MlbGameWithWeather): AstroddsGameScan {
  const { venueMapped, ...rest } = game;
  return venueMapped ? rest : rest;
}

function venueCoordinates(game: MlbGame) {
  const defaultCoordinates = game.venue?.location?.defaultCoordinates;
  if (typeof defaultCoordinates?.latitude === "number" && typeof defaultCoordinates.longitude === "number") {
    return {
      latitude: defaultCoordinates.latitude,
      longitude: defaultCoordinates.longitude,
    };
  }

  return findVenueCoordinates(game.venue?.name);
}

function firstSeasonPitchingStat(person?: MlbPerson) {
  return person?.stats?.flatMap((group) => group.splits ?? []).find((split) => split.stat)?.stat;
}

function pitcherContext(ref?: MlbPitcherRef, people = new Map<number, MlbPerson>()): AstroddsMlbPitcherContext {
  if (!ref?.fullName) {
    return {
      sourceStatus: "NOT_CONNECTED",
      summary: "Probable pitcher not posted by MLB StatsAPI.",
    };
  }

  const person = typeof ref.id === "number" ? people.get(ref.id) : undefined;
  const stat = firstSeasonPitchingStat(person);
  const handedness = person?.pitchHand?.description ?? ref.pitchHand?.description ?? ref.pitchHand?.code;
  const era = safeNumber(stat?.era);
  const whip = safeNumber(stat?.whip);
  const strikeOuts = safeNumber(stat?.strikeOuts);
  const wins = safeNumber(stat?.wins);
  const losses = safeNumber(stat?.losses);
  const sourceStatus: AstroddsSourceStatus = stat ? "CONNECTED" : "PARTIAL";
  const statParts = [
    handedness ? handedness : "hand unknown",
    typeof era === "number" ? `ERA ${era.toFixed(2)}` : "ERA missing",
    typeof strikeOuts === "number" ? `${strikeOuts} SO` : "SO missing",
  ];

  return {
    id: ref.id,
    name: ref.fullName,
    handedness,
    era,
    whip,
    strikeOuts,
    wins,
    losses,
    sourceStatus,
    summary: `${ref.fullName} (${statParts.join(", ")})`,
  };
}

function standingsRecords(data?: MlbStandingsResponse) {
  const records = new Map<number, AstroddsMlbTeamRecord>();
  for (const record of data?.records ?? []) {
    for (const teamRecord of record.teamRecords ?? []) {
      const teamId = teamRecord.team?.id;
      const teamName = teamRecord.team?.name ?? "Unknown team";
      if (typeof teamId !== "number") continue;
      const wins = teamRecord.leagueRecord?.wins;
      const losses = teamRecord.leagueRecord?.losses;
      const pct = safeNumber(teamRecord.leagueRecord?.pct);
      const streak = teamRecord.streak?.streakCode ??
        (teamRecord.streak?.streakType && teamRecord.streak.streakNumber ? `${teamRecord.streak.streakType}${teamRecord.streak.streakNumber}` : undefined);

      records.set(teamId, {
        teamId,
        teamName,
        wins,
        losses,
        winningPercentage: pct,
        streak,
        sourceStatus: typeof wins === "number" && typeof losses === "number" ? "CONNECTED" : "PARTIAL",
        summary: typeof wins === "number" && typeof losses === "number"
          ? `${teamName}: ${wins}-${losses}${streak ? `, ${streak}` : ""}`
          : `${teamName}: record partial`,
      });
    }
  }
  return records;
}

function recentForm(data?: MlbScheduleResponse) {
  const forms = new Map<number, RecentTeamForm>();

  function update(team?: MlbGameTeam, opponent?: MlbGameTeam) {
    const teamId = team?.team?.id;
    const teamName = team?.team?.name ?? "Unknown team";
    const scoreFor = team?.score;
    const scoreAgainst = opponent?.score;
    if (typeof teamId !== "number" || typeof scoreFor !== "number" || typeof scoreAgainst !== "number") return;
    const current = forms.get(teamId) ?? {
      teamId,
      teamName,
      games: 0,
      wins: 0,
      losses: 0,
      runsFor: 0,
      runsAgainst: 0,
    };
    current.games += 1;
    current.wins += scoreFor > scoreAgainst ? 1 : 0;
    current.losses += scoreFor < scoreAgainst ? 1 : 0;
    current.runsFor += scoreFor;
    current.runsAgainst += scoreAgainst;
    forms.set(teamId, current);
  }

  for (const day of data?.dates ?? []) {
    for (const game of day.games ?? []) {
      if (liveStatus(game) !== "FINAL") continue;
      update(game.teams?.away, game.teams?.home);
      update(game.teams?.home, game.teams?.away);
    }
  }

  return forms;
}

function mergeRecord(teamId: number | undefined, teamName: string, standings: Map<number, AstroddsMlbTeamRecord>, forms: Map<number, RecentTeamForm>) {
  if (typeof teamId !== "number") {
    return {
      teamName,
      sourceStatus: "NOT_CONNECTED" as const,
      summary: `${teamName}: team record not connected.`
    } satisfies AstroddsMlbTeamRecord;
  }

  const standing = standings.get(teamId);
  const form = forms.get(teamId);
  const sourceStatus: AstroddsSourceStatus = standing && form ? "CONNECTED" : standing || form ? "PARTIAL" : "NOT_CONNECTED";
  const recentSummary = form
    ? `last ${form.games}: ${form.wins}-${form.losses}, RF ${form.runsFor}, RA ${form.runsAgainst}`
    : "recent form missing";

  return {
    teamId,
    teamName: standing?.teamName ?? form?.teamName ?? teamName,
    wins: standing?.wins,
    losses: standing?.losses,
    winningPercentage: standing?.winningPercentage,
    streak: standing?.streak,
    recentGames: form?.games,
    recentWins: form?.wins,
    recentLosses: form?.losses,
    recentRunsFor: form?.runsFor,
    recentRunsAgainst: form?.runsAgainst,
    sourceStatus,
    summary: `${standing?.summary ?? `${teamName}: season record missing`}; ${recentSummary}`,
  };
}

function gradeFromDataQuality(score: number) {
  if (score >= 80) return "A" as const;
  if (score >= 65) return "B" as const;
  if (score >= 50) return "C" as const;
  if (score >= 35) return "D" as const;
  return "F" as const;
}

function clamp(value: number, min = 0, max = 100) {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, Math.round(value)));
}

function pitcherRating(pitcher?: AstroddsMlbPitcherContext) {
  if (!pitcher?.name) return 0;
  let rating = 0;
  if (typeof pitcher.era === "number") rating += (4.4 - pitcher.era) * 5;
  if (typeof pitcher.whip === "number") rating += (1.32 - pitcher.whip) * 10;
  if (typeof pitcher.strikeOuts === "number") rating += Math.min(7, pitcher.strikeOuts / 35);
  if (typeof pitcher.wins === "number" && typeof pitcher.losses === "number") rating += Math.min(5, Math.max(-5, pitcher.wins - pitcher.losses));
  return Math.max(-16, Math.min(16, rating));
}

function teamRating(record?: AstroddsMlbTeamRecord) {
  if (!record) return 0;
  let rating = 0;
  if (typeof record.winningPercentage === "number") rating += (record.winningPercentage - 0.5) * 36;
  if (typeof record.recentWins === "number" && typeof record.recentGames === "number" && record.recentGames > 0) {
    rating += (record.recentWins / record.recentGames - 0.5) * 18;
  }
  if (typeof record.recentRunsFor === "number" && typeof record.recentRunsAgainst === "number" && typeof record.recentGames === "number" && record.recentGames > 0) {
    rating += ((record.recentRunsFor - record.recentRunsAgainst) / record.recentGames) * 1.4;
  }
  return Math.max(-18, Math.min(18, rating));
}

function dataQualityScore(input: {
  awayPitcher: AstroddsMlbPitcherContext;
  homePitcher: AstroddsMlbPitcherContext;
  awayRecord: AstroddsMlbTeamRecord;
  homeRecord: AstroddsMlbTeamRecord;
  weather?: AstroddsWeatherContext;
  venue?: string;
  linescoreConnected: boolean;
}) {
  let score = 20;
  if (input.awayPitcher.name && input.homePitcher.name) score += 15;
  else if (input.awayPitcher.name || input.homePitcher.name) score += 8;
  if (input.awayPitcher.sourceStatus === "CONNECTED" && input.homePitcher.sourceStatus === "CONNECTED") score += 13;
  else if (input.awayPitcher.sourceStatus !== "NOT_CONNECTED" || input.homePitcher.sourceStatus !== "NOT_CONNECTED") score += 6;
  if (input.awayRecord.winningPercentage !== undefined && input.homeRecord.winningPercentage !== undefined) score += 12;
  if (input.awayRecord.recentGames && input.homeRecord.recentGames) score += 10;
  if (input.weather?.status === "CONNECTED") score += 10;
  else if (input.weather?.status === "PARTIAL") score += 4;
  if (input.venue) score += 4;
  if (input.linescoreConnected) score += 4;
  return clamp(score);
}

function buildModelPick(input: {
  away: string;
  home: string;
  venue?: string;
  weather?: AstroddsWeatherContext;
  awayPitcher: AstroddsMlbPitcherContext;
  homePitcher: AstroddsMlbPitcherContext;
  awayRecord: AstroddsMlbTeamRecord;
  homeRecord: AstroddsMlbTeamRecord;
  liveStatus: ReturnType<typeof liveStatus>;
  linescoreConnected: boolean;
}): AstroddsMlbModelPick {
  const missingDataWarnings: string[] = [
    "Lineup source not connected - confirmed batting orders unavailable.",
    "Injury/news source not connected - late scratches unavailable.",
    "Bullpen availability not connected - reliever fatigue not modeled yet.",
  ];

  if (!input.awayPitcher.name || !input.homePitcher.name) missingDataWarnings.push("Starting pitcher unknown for one or both teams.");
  if (input.awayPitcher.name && input.awayPitcher.sourceStatus !== "CONNECTED") missingDataWarnings.push(`${input.awayPitcher.name} season pitching stats are partial.`);
  if (input.homePitcher.name && input.homePitcher.sourceStatus !== "CONNECTED") missingDataWarnings.push(`${input.homePitcher.name} season pitching stats are partial.`);
  if (input.awayRecord.sourceStatus !== "CONNECTED" || input.homeRecord.sourceStatus !== "CONNECTED") missingDataWarnings.push("Team record or recent form is partial.");
  if (input.weather?.status !== "CONNECTED") missingDataWarnings.push("Weather is partial or missing.");

  const pitcherScore = clamp(50 + (pitcherRating(input.homePitcher) - pitcherRating(input.awayPitcher)) * 1.6);
  const teamFormScore = clamp(50 + (teamRating(input.homeRecord) - teamRating(input.awayRecord)) * 1.4);
  const weatherScore = input.weather?.status === "CONNECTED" ? clamp(78 - (input.weather.impactScore ?? 0)) : 44;
  const lineupScore = 0;
  const injuryScore = 0;
  const qualityScore = dataQualityScore(input);
  const homeFieldBoost = 2.5;
  const homeAdvantage = (pitcherScore - 50) * 0.42 + (teamFormScore - 50) * 0.48 + homeFieldBoost;
  const weatherRiskPenalty = input.weather?.impact === "HIGH" ? 7 : input.weather?.impact === "MEDIUM" ? 4 : 0;
  const rawConfidence = 50 + Math.abs(homeAdvantage) * 1.35 - weatherRiskPenalty;
  let modelConfidence = clamp(rawConfidence);

  if (qualityScore < 45) modelConfidence = Math.min(modelConfidence, 58);
  else if (qualityScore < 60) modelConfidence = Math.min(modelConfidence, 66);
  else if (qualityScore < 75) modelConfidence = Math.min(modelConfidence, 76);
  modelConfidence = Math.min(modelConfidence, 82); // lineups/injuries/bullpen are not connected yet.

  const modelScore = clamp(modelConfidence * 0.68 + qualityScore * 0.32);
  const modelLeanSide = modelConfidence >= 58 && modelScore >= 55 ? (homeAdvantage >= 0 ? "HOME" : "AWAY") : "WAIT";
  const modelLeanTeam = modelLeanSide === "HOME" ? input.home : modelLeanSide === "AWAY" ? input.away : undefined;
  const dataQuality = gradeFromDataQuality(qualityScore);
  const positiveFactors = [
    input.awayPitcher.name && input.homePitcher.name ? "probable pitchers posted" : "pitcher data incomplete",
    input.awayRecord.winningPercentage !== undefined && input.homeRecord.winningPercentage !== undefined ? "season records connected" : "season records partial",
    input.awayRecord.recentGames && input.homeRecord.recentGames ? "recent form connected" : "recent form partial",
    input.weather?.status === "CONNECTED" ? "weather connected" : "weather partial",
    input.venue ? `venue ${input.venue}` : "venue missing",
  ];
  const leanText = modelLeanTeam ? `${modelLeanTeam} lean` : "no side lean";

  return {
    modelLeanSide,
    modelLeanTeam,
    modelConfidence,
    modelScore,
    dataQuality,
    dataQualityScore: qualityScore,
    pitcherScore,
    lineupScore,
    injuryScore,
    teamFormScore,
    weatherScore,
    modelReason:
      modelLeanSide === "WAIT"
        ? `WAIT - model confidence is too low from available MLB StatsAPI data (${positiveFactors.join(", ")}).`
        : `${leanText}: StatsAPI data favors ${modelLeanTeam}. Inputs: ${positiveFactors.join(", ")}. Official bet blocked until real odds are matched.`,
    missingDataWarnings: Array.from(new Set(missingDataWarnings)),
    officialBetBlockedReason: "No official bet - no matched Polymarket entry price.",
    action: modelLeanSide === "WAIT" ? "WAIT" : "WAIT_FOR_ODDS",
  };
}

function pitcherSummary(away: string, home: string, awayPitcher: AstroddsMlbPitcherContext, homePitcher: AstroddsMlbPitcherContext) {
  if (awayPitcher.name || homePitcher.name) {
    return `${away}: ${awayPitcher.summary} | ${home}: ${homePitcher.summary}`;
  }
  return "Probable pitchers not posted yet.";
}

export async function scanMLBGamesWithDiagnostics(signal?: AbortSignal): Promise<{
  games: AstroddsGameScan[];
  sportApi: AstroddsScanDiagnostics["sportApi"];
  weather: AstroddsScanDiagnostics["weather"];
  sourceDiagnostics: AstroddsSourceDiagnostic[];
}> {
  const url = mlbScheduleUrl();
  const sourceDiagnostics: AstroddsSourceDiagnostic[] = [];
  let data: MlbScheduleResponse;
  try {
    data = await fetchJson<MlbScheduleResponse>(url, signal, sourceDiagnostics, "schedule");
  } catch (error) {
    const message = `MLB API schedule fetch failed: ${error instanceof Error ? error.message : "unknown error"}.`;
    return {
      games: [],
      sportApi: {
        sport: "MLB",
        status: "FAILED",
        sourceMode: "FAILED",
        gamesFetched: 0,
        uniqueGamesFetched: 0,
        duplicateGamesRemoved: 0,
        probablePitchersFound: 0,
        venuesFound: 0,
        error: message,
        sourceUrl: url.toString(),
      },
      weather: {
        status: "NOT_CONNECTED",
        sourceMode: "FAILED",
        gamesWithMappedCityOrStadium: 0,
        weatherResultsFetched: 0,
        error: "Weather skipped because MLB schedule rows were unavailable.",
        sourceUrl: OPEN_METEO_FORECAST_URL,
      },
      sourceDiagnostics,
    };
  }
  const games = data.dates?.flatMap((day) => day.games ?? []) ?? [];
  const probablePitchersFound = games.filter(hasProbablePitcher).length;
  const gamesWithBothPitchers = games.filter(hasBothProbablePitchers).length;
  const venuesFound = games.filter((game) => Boolean(game.venue?.name)).length;
  const pitcherIds = Array.from(
    new Set(
      games
        .flatMap((game) => [game.teams?.away?.probablePitcher?.id, game.teams?.home?.probablePitcher?.id])
        .filter((id): id is number => typeof id === "number"),
    ),
  );

  let standings = new Map<number, AstroddsMlbTeamRecord>();
  let forms = new Map<number, RecentTeamForm>();
  let people = new Map<number, MlbPerson>();
  const supplementalErrors: string[] = [];

  try {
    standings = standingsRecords(await fetchJson<MlbStandingsResponse>(mlbStandingsUrl(), signal, sourceDiagnostics, "standings"));
  } catch (error) {
    supplementalErrors.push(`Standings fetch failed: ${error instanceof Error ? error.message : "unknown error"}.`);
  }

  try {
    forms = recentForm(await fetchJson<MlbScheduleResponse>(mlbRecentResultsUrl(), signal, sourceDiagnostics, "recent-results"));
  } catch (error) {
    supplementalErrors.push(`Recent results fetch failed: ${error instanceof Error ? error.message : "unknown error"}.`);
  }

  if (pitcherIds.length) {
    try {
      const peoplePayload = await fetchJson<MlbPeopleResponse>(mlbPeopleUrl(pitcherIds), signal, sourceDiagnostics, "pitcher-details");
      people = new Map((peoplePayload.people ?? []).filter((person) => typeof person.id === "number").map((person) => [person.id as number, person]));
    } catch (error) {
      supplementalErrors.push(`Pitcher detail fetch failed: ${error instanceof Error ? error.message : "unknown error"}.`);
    }
  }

  const rows = await Promise.all(
    games.map(async (game) => {
      const away = game.teams?.away?.team?.name ?? "Away";
      const home = game.teams?.home?.team?.name ?? "Home";
      const awayTeamId = game.teams?.away?.team?.id;
      const homeTeamId = game.teams?.home?.team?.id;
      const venue = game.venue?.name;
      const coords = venueCoordinates(game);
      const weather = await fetchWeatherContext(
        {
          latitude: coords?.latitude,
          longitude: coords?.longitude,
          startTime: game.gameDate,
          sport: "MLB",
        },
        signal,
      );
      const awayPitcher = pitcherContext(game.teams?.away?.probablePitcher, people);
      const homePitcher = pitcherContext(game.teams?.home?.probablePitcher, people);
      const awayRecord = mergeRecord(awayTeamId, away, standings, forms);
      const homeRecord = mergeRecord(homeTeamId, home, standings, forms);
      const status = liveStatus(game);
      const lineupsStatus = status === "LIVE" || status === "FINAL" ? "PARTIAL" : "NOT_CONNECTED";
      const linescoreConnected = Boolean(game.linescore?.currentInningOrdinal || game.linescore?.inningState);
      const modelPick = buildModelPick({
        away,
        home,
        venue,
        weather,
        awayPitcher,
        homePitcher,
        awayRecord,
        homeRecord,
        liveStatus: status,
        linescoreConnected,
      });
      const keyPlayerStatus = pitcherSummary(away, home, awayPitcher, homePitcher);
      const statsApiHealth: AstroddsMlbGameContext["statsApiHealth"] = {
        schedule: "CONNECTED",
        standings: awayRecord.winningPercentage !== undefined && homeRecord.winningPercentage !== undefined ? "CONNECTED" : standings.size ? "PARTIAL" : "NOT_CONNECTED",
        recentForm: awayRecord.recentGames && homeRecord.recentGames ? "CONNECTED" : forms.size ? "PARTIAL" : "NOT_CONNECTED",
        pitcherDetails: awayPitcher.sourceStatus === "CONNECTED" && homePitcher.sourceStatus === "CONNECTED" ? "CONNECTED" : people.size ? "PARTIAL" : "NOT_CONNECTED",
        linescore: linescoreConnected ? "CONNECTED" : status === "PRE_GAME" ? "PARTIAL" : "NOT_CONNECTED",
      };

      return {
        id: `mlb-${game.gamePk}`,
        sport: "MLB",
        league: "MLB",
        game: `${away} vs ${home}`,
        awayTeam: away,
        homeTeam: home,
        startTime: game.gameDate,
        liveStatus: status,
        score: score(game),
        period: game.linescore?.currentInningOrdinal
          ? `${game.linescore.currentInningOrdinal} ${game.linescore.inningState ?? ""}`.trim()
          : game.status?.detailedState ?? "Pregame",
        venue,
        weather,
        mlbStatus: {
          abstractGameState: game.status?.abstractGameState,
          detailedState: game.status?.detailedState,
          codedGameState: game.status?.codedGameState,
          officialDate: game.gameDate,
          normalized: status,
        },
        injuries: {
          status: "NOT_CONNECTED",
          source: "Source needed",
          summary: "NOT CONNECTED - MLB injury/news provider needed; confidence capped.",
        },
        lineups: {
          status: lineupsStatus,
          source: "MLB StatsAPI schedule",
          summary:
            lineupsStatus === "PARTIAL"
              ? "PARTIAL - game status/linescore connected; confirmed batting orders still require a lineup source."
              : "NOT CONNECTED - confirmed starting lineups not available from this free schedule feed.",
        },
        keyContext: [
          `Probable pitchers: ${keyPlayerStatus}`,
          `Team records: ${awayRecord.summary} | ${homeRecord.summary}`,
          `Model pick: ${modelPick.modelLeanTeam ?? "WAIT"} (${modelPick.modelConfidence}% confidence, data ${modelPick.dataQuality}).`,
          weather.summary,
          "Bullpen fatigue, injury/news, and confirmed lineups are not connected; confidence is capped honestly.",
        ],
        keyPlayerStatus,
        markets: [],
        dataStatus: dataStatusRank(["CONNECTED", weather.status, lineupsStatus, awayPitcher.sourceStatus, homePitcher.sourceStatus, awayRecord.sourceStatus, homeRecord.sourceStatus]),
        source: "MLB StatsAPI v1 schedule, standings, recent results, pitcher details + Open-Meteo weather",
        mlbContext: {
          gamePk: game.gamePk,
          awayTeamId,
          homeTeamId,
          awayRecord,
          homeRecord,
          awayPitcher,
          homePitcher,
          statsApiHealth,
        },
        modelPick,
        venueMapped: Boolean(coords),
      } satisfies MlbGameWithWeather;
    }),
  );

  const gamesWithMappedCityOrStadium = rows.filter((game) => game.venueMapped).length;
  const weatherResultsFetched = rows.filter((game) => game.weather?.status === "CONNECTED").length;
  const missingPitchers = games.length - probablePitchersFound;
  const missingVenues = games.length - venuesFound;
  const unmappedVenues = games.length - gamesWithMappedCityOrStadium;
  const failedWeather = rows.filter((game) => game.weather?.status === "PARTIAL").length;
  const sportWarnings = [
    missingPitchers > 0 ? `Probable pitchers missing for ${missingPitchers} game${missingPitchers === 1 ? "" : "s"}.` : "",
    gamesWithBothPitchers < games.length ? `Both probable pitchers posted for ${gamesWithBothPitchers} of ${games.length} game${games.length === 1 ? "" : "s"}.` : "",
    missingVenues > 0 ? `Venues missing for ${missingVenues} game${missingVenues === 1 ? "" : "s"}.` : "",
    ...supplementalErrors,
  ].filter(Boolean);
  const weatherWarnings = [
    unmappedVenues > 0 ? `${unmappedVenues} venue${unmappedVenues === 1 ? "" : "s"} need location mapping.` : "",
    failedWeather > 0 ? `${failedWeather} weather request${failedWeather === 1 ? "" : "s"} returned partial data.` : "",
  ].filter(Boolean);

  return {
    games: rows.map(stripVenueMapped),
    sportApi: {
      sport: "MLB",
      status: sportWarnings.length ? "PARTIAL" : "CONNECTED_SERVER",
      sourceMode: "SERVER",
      gamesFetched: games.length,
      uniqueGamesFetched: rows.length,
      duplicateGamesRemoved: Math.max(0, games.length - rows.length),
      probablePitchersFound,
      venuesFound,
      error: sportWarnings.length ? sportWarnings.join(" ") : undefined,
      sourceUrl: url.toString(),
    },
    weather: {
      status:
        games.length === 0
          ? "NOT_CONNECTED"
          : gamesWithMappedCityOrStadium === 0
            ? "NOT_CONNECTED"
            : weatherResultsFetched === gamesWithMappedCityOrStadium && unmappedVenues === 0
              ? "CONNECTED_SERVER"
              : "PARTIAL",
      sourceMode: gamesWithMappedCityOrStadium > 0 || weatherResultsFetched > 0 ? "SERVER" : "FAILED",
      gamesWithMappedCityOrStadium,
      weatherResultsFetched,
      error: weatherWarnings.length ? weatherWarnings.join(" ") : undefined,
      sourceUrl: OPEN_METEO_FORECAST_URL,
    },
    sourceDiagnostics,
  };
}

export async function scanMLBGames(signal?: AbortSignal): Promise<AstroddsGameScan[]> {
  const payload = await scanMLBGamesWithDiagnostics(signal);
  return payload.games;
}
