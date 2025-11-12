function ensureAbsoluteHttpBase(url: string | undefined): string {
  const fallback = "http://localhost:8001/api/v1";
  const value = (url ?? "").trim();

  const effectiveOrigin =
    typeof window !== "undefined" && window.location?.origin?.startsWith("http")
      ? window.location.origin
      : fallback;

  if (!value) {
    return fallback;
  }

  if (value.startsWith("http://") || value.startsWith("https://")) {
    return value.replace(/\/$/, "");
  }

  if (value.startsWith("/")) {
    return `${effectiveOrigin}${value}`.replace(/\/$/, "");
  }

  return `${effectiveOrigin}/${value}`.replace(/\/$/, "");
}

function ensureAbsoluteWsBase(url: string | undefined): string | null {
  if (!url) {
    return null;
  }

  const trimmed = url.trim();
  if (trimmed.startsWith("ws://") || trimmed.startsWith("wss://")) {
    return trimmed.replace(/\/$/, "");
  }

  return normalizeWebSocketBase(ensureAbsoluteHttpBase(trimmed));
}

const API_BASE = ensureAbsoluteHttpBase(import.meta.env.VITE_API_BASE);

function normalizeWebSocketBase(httpUrl: string): string {
  if (httpUrl.startsWith("https://")) {
    return `wss://${httpUrl.slice("https://".length).replace(/\/$/, "")}`;
  }
  if (httpUrl.startsWith("http://")) {
    return `ws://${httpUrl.slice("http://".length).replace(/\/$/, "")}`;
  }
  return httpUrl.replace(/\/$/, "");
}

const DEFAULT_WS_BASE = `${normalizeWebSocketBase(API_BASE)}/research/stream`;
const RESEARCH_WS_BASE = ensureAbsoluteWsBase(import.meta.env.VITE_RESEARCH_WS_BASE) ?? DEFAULT_WS_BASE;

export type ResearchStreamEventType =
  | "step"
  | "human_in_loop"
  | "human_response_ack"
  | "complete"
  | "error"
  | "cancelled";

export interface ResearchStreamEvent {
  type: ResearchStreamEventType;
  task_id: string;
  timestamp?: string;
  data?: Record<string, unknown>;
}

interface StreamHandlers {
  onEvent: (event: ResearchStreamEvent) => void;
  onError?: (error: Event | Error) => void;
  onClose?: () => void;
}

export class ResearchStreamClient {
  private socket: WebSocket | null = null;

  connect(taskId: string, handlers: StreamHandlers) {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    // 直接使用完整 WebSocket URL（避免相对路径解析问题）
    const wsUrl = `${RESEARCH_WS_BASE}?task_id=${encodeURIComponent(taskId)}`;

    const socket = new WebSocket(wsUrl);
    this.socket = socket;

    socket.addEventListener("message", (event) => {
      try {
        const payload = JSON.parse(event.data as string) as ResearchStreamEvent;
        handlers.onEvent(payload);
      } catch (error) {
        console.error("[ResearchStream] 消息解析失败", error);
      }
    });

    socket.addEventListener("error", (event) => {
      handlers.onError?.(event);
    });

    socket.addEventListener("close", () => {
      this.socket = null;
      handlers.onClose?.();
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
