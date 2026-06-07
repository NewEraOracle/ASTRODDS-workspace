export type SafeFetchResult = {
  ok: boolean;
  url: string;
  httpStatus?: number;
  error?: string;
  cause?: string;
  timeout: boolean;
  tlsFallback?: boolean;
  responseTextSnippet?: string;
  json?: unknown;
  text?: string;
};

export type SafeFetchOptions = RequestInit & {
  timeoutMs?: number;
  parseJson?: boolean;
};

function errorText(error: unknown) {
  if (error instanceof Error) return error.message;
  return typeof error === "string" ? error : "Unknown fetch error.";
}

function shouldUsePolymarketTlsFallback(target: string, error: unknown) {
  let hostname = "";

  try {
    hostname = new URL(target).hostname;
  } catch {
    return false;
  }

  const detail = [errorText(error), error instanceof Error && error.cause ? String(error.cause) : ""].join(" ").toLowerCase();
  return (
    hostname.endsWith("polymarket.com") &&
    (detail.includes("certificate") || detail.includes("cert") || detail.includes("unable to verify") || detail.includes("tls"))
  );
}

function headersToRecord(headers: HeadersInit | undefined) {
  if (!headers) return undefined;
  if (headers instanceof Headers) return Object.fromEntries(headers.entries());
  if (Array.isArray(headers)) return Object.fromEntries(headers);
  return headers;
}

async function nodeHttpsTlsFallback(target: string, options: SafeFetchOptions, timeoutMs: number): Promise<SafeFetchResult> {
  const [{ default: https }] = await Promise.all([import("node:https")]);
  const url = new URL(target);

  return new Promise((resolve) => {
    const request = https.request(
      url,
      {
        method: options.method ?? "GET",
        headers: headersToRecord(options.headers),
        timeout: timeoutMs,
        rejectUnauthorized: false,
      },
      (response) => {
        const chunks: Buffer[] = [];

        response.on("data", (chunk: Buffer) => chunks.push(chunk));
        response.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          const snippet = text ? text.slice(0, 500) : undefined;
          let json: unknown;

          if (options.parseJson !== false && text) {
            try {
              json = JSON.parse(text) as unknown;
            } catch {
              json = undefined;
            }
          }

          resolve({
            ok: Boolean(response.statusCode && response.statusCode >= 200 && response.statusCode < 300),
            url: target,
            httpStatus: response.statusCode,
            error: response.statusCode && response.statusCode >= 200 && response.statusCode < 300 ? undefined : `HTTP ${response.statusCode}`,
            timeout: false,
            tlsFallback: true,
            responseTextSnippet: snippet,
            json,
            text,
          });
        });
      },
    );

    request.on("timeout", () => {
      request.destroy();
      resolve({
        ok: false,
        url: target,
        error: `Timed out after ${timeoutMs}ms`,
        timeout: true,
        tlsFallback: true,
      });
    });

    request.on("error", (error) => {
      resolve({
        ok: false,
        url: target,
        error: errorText(error),
        cause: error.cause ? String(error.cause) : undefined,
        timeout: false,
        tlsFallback: true,
      });
    });

    if (options.body && typeof options.body === "string") request.write(options.body);
    request.end();
  });
}

export async function safeFetch(url: string | URL, options: SafeFetchOptions = {}): Promise<SafeFetchResult> {
  const target = url.toString();
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? 10_000;
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(target, {
      ...options,
      signal: options.signal ?? controller.signal,
    });
    const text = await response.text().catch(() => "");
    const snippet = text ? text.slice(0, 500) : undefined;
    let json: unknown;

    if (options.parseJson !== false && text) {
      try {
        json = JSON.parse(text) as unknown;
      } catch {
        json = undefined;
      }
    }

    return {
      ok: response.ok,
      url: target,
      httpStatus: response.status,
      error: response.ok ? undefined : `HTTP ${response.status}`,
      timeout: false,
      responseTextSnippet: snippet,
      json,
      text,
    };
  } catch (error) {
    const timeoutError = error instanceof Error && error.name === "AbortError";

    if (!timeoutError && shouldUsePolymarketTlsFallback(target, error)) {
      return nodeHttpsTlsFallback(target, options, timeoutMs);
    }

    return {
      ok: false,
      url: target,
      error: timeoutError ? `Timed out after ${timeoutMs}ms` : errorText(error),
      cause: error instanceof Error && error.cause ? String(error.cause) : undefined,
      timeout: timeoutError,
    };
  } finally {
    clearTimeout(timeout);
  }
}

export async function safeFetchJson(url: string | URL, options: SafeFetchOptions = {}) {
  const result = await safeFetch(url, {
    ...options,
    parseJson: true,
    headers: {
      accept: "application/json",
      ...(options.headers ?? {}),
    },
  });

  if (!result.ok) {
    const detail = [result.error, result.cause, result.responseTextSnippet].filter(Boolean).join(" | ");
    throw new Error(`${result.url}: ${detail || "fetch failed"}`);
  }

  return result.json;
}
