import type { AstroddsWeatherContext } from "./types";
import { safeNumber } from "./normalize";

type WeatherPoint = {
  latitude?: number;
  longitude?: number;
  startTime?: string;
  sport?: string;
};

type OpenMeteoResponse = {
  current?: {
    temperature_2m?: number;
    relative_humidity_2m?: number;
    precipitation?: number;
    wind_speed_10m?: number;
    wind_direction_10m?: number;
  };
  hourly?: {
    time?: string[];
    temperature_2m?: number[];
    relative_humidity_2m?: number[];
    precipitation_probability?: number[];
    precipitation?: number[];
    wind_speed_10m?: number[];
    wind_direction_10m?: number[];
  };
};

export const OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast";

const fFromC = (value?: number) => (typeof value === "number" ? Math.round((value * 9) / 5 + 32) : undefined);
const kmhToMph = (value?: number) => (typeof value === "number" ? Math.round(value * 0.621371) : undefined);

function weatherImpactScore(context: {
  windMph?: number;
  precipitationProbability?: number;
  temperatureF?: number;
  sport?: string;
}) {
  let score = 0;

  if ((context.windMph ?? 0) >= 15) score += context.sport === "MLB" || context.sport === "NFL" ? 30 : 18;
  if ((context.windMph ?? 0) >= 25) score += 20;
  if ((context.precipitationProbability ?? 0) >= 35) score += 18;
  if ((context.precipitationProbability ?? 0) >= 65) score += 22;
  if ((context.temperatureF ?? 70) <= 38 || (context.temperatureF ?? 70) >= 92) score += 12;

  return Math.max(0, Math.min(100, score));
}

function summarizeWeather(score: number, windMph?: number, precipitationProbability?: number, temperatureF?: number) {
  if (score >= 55) return `High weather impact: ${temperatureF ?? "--"}F, ${windMph ?? "--"} mph wind, ${precipitationProbability ?? "--"}% precip.`;
  if (score >= 25) return `Medium weather impact: ${temperatureF ?? "--"}F, ${windMph ?? "--"} mph wind, ${precipitationProbability ?? "--"}% precip.`;
  return `Low weather impact: ${temperatureF ?? "--"}F, ${windMph ?? "--"} mph wind, ${precipitationProbability ?? "--"}% precip.`;
}

function nearestHourlyIndex(times: string[] = [], startTime?: string) {
  if (!startTime || !times.length) return 0;
  const target = new Date(startTime).getTime();
  let bestIndex = 0;
  let bestDistance = Number.POSITIVE_INFINITY;

  times.forEach((time, index) => {
    const distance = Math.abs(new Date(time).getTime() - target);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  });

  return bestIndex;
}

export function openMeteoForecastUrl(point: WeatherPoint) {
  const url = new URL(OPEN_METEO_FORECAST_URL);
  url.searchParams.set("latitude", String(point.latitude));
  url.searchParams.set("longitude", String(point.longitude));
  url.searchParams.set("current", "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m");
  url.searchParams.set("hourly", "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m,wind_direction_10m");
  url.searchParams.set("temperature_unit", "celsius");
  url.searchParams.set("wind_speed_unit", "kmh");
  url.searchParams.set("forecast_days", "7");
  url.searchParams.set("timezone", "auto");
  return url;
}

export async function fetchWeatherContext(point: WeatherPoint, signal?: AbortSignal): Promise<AstroddsWeatherContext> {
  if (typeof point.latitude !== "number" || typeof point.longitude !== "number") {
    return {
      status: "NOT_CONNECTED",
      source: "Open-Meteo",
      impactScore: 0,
      impact: "NONE",
      summary: "NOT CONNECTED - venue coordinates needed for weather.",
    };
  }

  try {
    const url = openMeteoForecastUrl(point);

    const response = await fetch(url, {
      signal,
      next: { revalidate: 900 },
      headers: { accept: "application/json" },
    });

    if (!response.ok) throw new Error(`Open-Meteo returned ${response.status}`);

    const data = (await response.json()) as OpenMeteoResponse;
    const index = nearestHourlyIndex(data.hourly?.time, point.startTime);
    const temperatureF = fFromC(safeNumber(data.hourly?.temperature_2m?.[index]) ?? safeNumber(data.current?.temperature_2m));
    const windMph = kmhToMph(safeNumber(data.hourly?.wind_speed_10m?.[index]) ?? safeNumber(data.current?.wind_speed_10m));
    const precipitationProbability = safeNumber(data.hourly?.precipitation_probability?.[index]) ?? safeNumber(data.current?.precipitation);
    const humidity = safeNumber(data.hourly?.relative_humidity_2m?.[index]) ?? safeNumber(data.current?.relative_humidity_2m);
    const windDirection = safeNumber(data.hourly?.wind_direction_10m?.[index]) ?? safeNumber(data.current?.wind_direction_10m);
    const impactScore = weatherImpactScore({ windMph, precipitationProbability, temperatureF, sport: point.sport });

    return {
      status: "CONNECTED",
      source: "Open-Meteo",
      temperatureF,
      windMph,
      windDirection,
      precipitationProbability,
      humidity,
      impactScore,
      impact: impactScore >= 55 ? "HIGH" : impactScore >= 25 ? "MEDIUM" : impactScore > 0 ? "LOW" : "NONE",
      summary: summarizeWeather(impactScore, windMph, precipitationProbability, temperatureF),
    };
  } catch (error) {
    return {
      status: "PARTIAL",
      source: "Open-Meteo",
      impactScore: 0,
      impact: "NONE",
      summary: `PARTIAL - weather fetch failed: ${error instanceof Error ? error.message : "unknown error"}.`,
    };
  }
}
