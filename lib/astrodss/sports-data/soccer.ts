import type { AstroddsGameScan } from "./types";
import { scanSportsDbLeague } from "./sportsdb";

export function scanSoccerGames(signal?: AbortSignal): Promise<AstroddsGameScan[]> {
  return scanSportsDbLeague(
    {
      sport: "SOCCER",
      league: "English Premier League",
      leagueId: "4328",
      weatherRelevant: true,
      keyPlayerLabel: "Starting XI / draw risk",
      sourceNote: "PARTIAL - EPL free schedule only; starting XI, xG, injuries, motivation, and red-card live state need a provider.",
    },
    signal,
  );
}
