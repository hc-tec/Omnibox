import axios from "axios";
import type {
  ChatRequestParams,
  PanelResponse,
  StreamMessage,
  StreamRequestPayload,
} from "../shared/types/panel";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";
const WS_BASE = import.meta.env.VITE_WS_BASE ?? "ws://localhost:8000/api/v1/chat/stream";

export async function requestPanel(params: ChatRequestParams): Promise<PanelResponse> {
  const response = await axios.post<PanelResponse>(`${API_BASE}/chat`, {
    query: params.query,
    filter_datasource: params.filter_datasource ?? null,
    use_cache: params.use_cache ?? true,
  });
  return response.data;
}

type StreamHandler = (message: StreamMessage) => void;
type ErrorHandler = (error: Event | Error) => void;

export class PanelStreamClient {
  private socket: WebSocket | null = null;
  private handler: StreamHandler | null = null;
  private errorHandler: ErrorHandler | null = null;

  connect(
    payload: StreamRequestPayload,
    onMessage: StreamHandler,
    onError?: ErrorHandler
  ): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    this.handler = onMessage;
    this.errorHandler = onError ?? null;

    const socket = new WebSocket(WS_BASE);
    this.socket = socket;

    socket.addEventListener("open", () => {
      socket.send(
        JSON.stringify({
          query: payload.query,
          filter_datasource: payload.filter_datasource ?? null,
          use_cache: payload.use_cache ?? true,
        })
      );
    });

    socket.addEventListener("message", (event) => {
      if (!this.handler) return;
      try {
        const parsed = JSON.parse(event.data as string) as StreamMessage;
        this.handler(parsed);
      } catch (err) {
        console.error("[PanelStream] 消息解析失败", err);
      }
    });

    socket.addEventListener("error", (event) => {
      this.errorHandler?.(event);
    });

    socket.addEventListener("close", () => {
      this.socket = null;
      this.handler = null;
      this.errorHandler = null;
    });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
