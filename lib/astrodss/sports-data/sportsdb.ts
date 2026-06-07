import type { AstroddsGameScan, AstroddsSport } from "./types";
import { compactId, liveStatusFromText } from "./normalize";
import { fetchWeatherContext } from "./weather";

type SportsDbEvent = {
  idEvent?: string;
  strEvent?: string;
  strLeague?: string;
  strSport?: string;
  strHomeTeam?: string;
  strAwayTeam?: string;
  strTimestamp?: string;
  dateEvent?: string;
  strTime?: string;
  strVenue?: string;
  intHomeScore?: string;
  intAwayScore?: string;
  strStatus?: string;
  strRound?: string;
  strSeason?: string;
};

type SportsDbResponse = {
  events?: SportsDbEvent[] | null;
};

export type SportsDbLeagueConfig = {
  sport: AstroddsSport;
  league: string;
  leagueId: string;
  weatherRelevant: boolean;
  keyPlayerLabel: string;
  sourceNote: string;
};

const FREE_KEY = "123";

function eventStartTime(event: SportsDbEvent) {
  if (event.strTimestamp) return event.strTimestamp;
  if (event.dateEvent && event.strTime) return `${event.dateEvent}T${event.strTime.replace(" ", "")}`;
  if (event.dateEvent) return `${event.dateEvent}T00:00:00Z`;
  return undefined;
}

function eventScore(event: SportsDbEvent) {
  if (event.intAwayScore || event.intHomeScore) return `${event.intAwayScore ?? 0}-${event.intHomeScore ?? 0}`;
  return "0-0";
}

export async function scanSportsDbLeague(config: SportsDbLeagueConfig, signal?: AbortSignal): Promise<AstroddsGameScan[]> {
  const url = `https://www.thesportsdb.com/api/v1/json/${FREE_KEY}/eventsnextleague.php?id=${config.leagueId}`;
  const response = await fetch(url, {
    signal,
    next: { revalidate: 900 },
    headers: { accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`TheSportsDB returned ${response.status}`);
  }

  const data = (await response.json()) as SportsDbResponse;
  const events = data.events ?? [];

  return Promise.all(
    events.map(async (event) => {
      const startTime = eventStartTime(event);
      const weather = config.weatherRelevant
        ? await fetchWeatherContext({ startTime, sport: config.sport }, signal)
        : undefined;
      const away = event.strAwayTeam ?? event.strEvent?.split(" vs ")?.[0] ?? "Away";
      const home = event.strHomeTeam ?? event.strEvent?.split(" vs ")?.[1] ?? "Home";
      const game = event.strEvent ?? `${away} vs ${home}`;

      return {
        id: `${config.sport.toLowerCase()}-${event.idEvent ?? compactId(game)}`,
        sport: config.sport,
        league: event.strLeague ?? config.league,
        game,
        awayTeam: away,
        homeTeam: home,
        startTime,
        liveStatus: liveStatusFromText(event.strStatus ?? "PRE_GAME"),
        score: eventScore(event),
        period: event.strStatus ?? event.strRound ?? "Pregame",
        venue: event.strVenue,
        weather,
        injuries: {
          status: "NOT_CONNECTED",
          source: "Source needed",
          summary: "NOT CONNECTED - injury provider needed.",
        },
        lineups: {
          status: "NOT_CONNECTED",
          source: "Source needed",
          summary: "NOT CONNECTED - lineup/source feed needed.",
        },
        keyContext: [
          `${config.keyPlayerLabel}: NOT CONNECTED - source needed.`,
          config.sourceNote,
          event.strSeason ? `Season: ${event.strSeason}` : "Schedule context from free event feed.",
        ],
        keyPlayerStatus: `${config.keyPlayerLabel}: NOT CONNECTED - source needed.`,
        markets: [],
        dataStatus: "PARTIAL",
        source: "TheSportsDB free v1 schedule feed",
      } satisfies AstroddsGameScan;
    }),
  );
}
