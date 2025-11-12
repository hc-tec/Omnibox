const FALLBACK_HTTP_ORIGIN = "http://localhost:8003";
const DEFAULT_HTTP_PATH = "/api/v1";

function currentOrigin(): string | null {
  if (typeof window === "undefined" || !window.location?.origin) {
    return null;
  }
  return window.location.origin;
}

function normalize(url: string): string {
  return url.replace(/\/+$/, "");
}

function toAbsoluteUrl(value: string, origin: string): string {
  if (value.startsWith("http://") || value.startsWith("https://")) {
    return value;
  }
  if (value.startsWith("/")) {
    return `${origin}${value}`;
  }
  return `${origin}/${value}`;
}

function convertHttpToWs(url: string): string {
  if (url.startsWith("https://")) {
    return `wss://${url.slice("https://".length)}`;
  }
  if (url.startsWith("http://")) {
    return `ws://${url.slice("http://".length)}`;
  }
  return url;
}

function extractOrigin(url: string): string | null {
  try {
    const parsed = new URL(url);
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return null;
  }
}

function ensureLeadingSlash(path: string): string {
  if (!path.startsWith("/")) {
    return `/${path}`;
  }
  return path;
}

export function resolveHttpBase(target?: string, defaultPath: string = DEFAULT_HTTP_PATH): string {
  const origin = currentOrigin() ?? FALLBACK_HTTP_ORIGIN;
  const trimmed = target?.trim();
  const candidate = trimmed && trimmed.length > 0 ? trimmed : defaultPath;
  const absolute = toAbsoluteUrl(candidate, origin);
  return normalize(absolute);
}

export function resolveWsBase(
  target?: string,
  defaultPath = `${DEFAULT_HTTP_PATH}/chat/stream`,
  httpBase?: string
): string {
  const trimmed = target?.trim();
  if (trimmed && trimmed.length > 0) {
    if (trimmed.startsWith("ws://") || trimmed.startsWith("wss://")) {
      return normalize(trimmed);
    }
    if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
      return normalize(convertHttpToWs(trimmed));
    }
    const origin = currentOrigin() ?? FALLBACK_HTTP_ORIGIN;
    return normalize(convertHttpToWs(toAbsoluteUrl(trimmed, origin)));
  }

  const originFromHttp =
    (httpBase && extractOrigin(httpBase)) ?? currentOrigin() ?? FALLBACK_HTTP_ORIGIN;
  const path = ensureLeadingSlash(defaultPath);
  const httpWithPath = `${originFromHttp}${path}`;
  return normalize(convertHttpToWs(httpWithPath));
}
