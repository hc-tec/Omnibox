const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8001/api/v1";

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
const RESEARCH_WS_BASE = import.meta.env.VITE_RESEARCH_WS_BASE ?? DEFAULT_WS_BASE;

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
