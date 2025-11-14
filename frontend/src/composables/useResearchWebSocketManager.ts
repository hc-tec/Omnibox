/**
 * 全局研究 WebSocket 连接管理器
 *
 * 解决问题：
 * - 主页面和详情页面共享同一个 WebSocket 连接
 * - 避免重复发送研究请求
 * - 确保研究进度数据的连续性
 */

import { ref } from "vue";
import { useResearchWebSocket } from "./useResearchWebSocket";

// 全局连接池：taskId -> WebSocket 连接实例
const activeConnections = ref<Map<string, ReturnType<typeof useResearchWebSocket>>>(new Map());

// 全局请求状态：taskId -> 是否已发送研究请求
const requestSent = ref<Map<string, boolean>>(new Map());

export interface WebSocketManagerOptions {
  taskId: string;
  autoReconnect?: boolean;
  reconnectDelay?: number;
  maxReconnectAttempts?: number;
}

/**
 * 获取或创建 WebSocket 连接
 * - 如果连接已存在，直接返回
 * - 如果连接不存在，创建新连接
 */
export function useResearchWebSocketManager(options: WebSocketManagerOptions) {
  const { taskId } = options;

  // 检查是否已有活跃连接
  let connection = activeConnections.value.get(taskId);

  if (!connection) {
    // 创建新连接
    console.log(`[WebSocketManager] 创建新连接: ${taskId}`);
    connection = useResearchWebSocket(options);
    activeConnections.value.set(taskId, connection);
  } else {
    console.log(`[WebSocketManager] 复用现有连接: ${taskId}`);
  }

  /**
   * 发送研究请求（带去重保护）
   * - 只有首次调用才会真正发送请求
   * - 后续调用会被忽略
   */
  function sendResearchRequestOnce(payload: {
    query: string;
    filter_datasource?: string | null;
    use_cache?: boolean;
    layout_snapshot?: any[] | null;
  }) {
    const alreadySent = requestSent.value.get(taskId);

    if (alreadySent) {
      console.log(`[WebSocketManager] 研究请求已发送，跳过: ${taskId}`);
      return;
    }

    console.log(`[WebSocketManager] 首次发送研究请求: ${taskId}`);
    connection!.sendResearchRequest(payload);
    requestSent.value.set(taskId, true);
  }

  /**
   * 断开连接并清理
   */
  function disconnectAndCleanup() {
    console.log(`[WebSocketManager] 断开并清理连接: ${taskId}`);
    connection?.disconnect();
    activeConnections.value.delete(taskId);
    requestSent.value.delete(taskId);
  }

  /**
   * 检查是否已发送研究请求
   */
  function hasRequestSent(): boolean {
    return requestSent.value.get(taskId) ?? false;
  }

  /**
   * 重置请求状态（用于重新发起研究）
   */
  function resetRequestState() {
    console.log(`[WebSocketManager] 重置请求状态: ${taskId}`);
    requestSent.value.delete(taskId);
  }

  return {
    // 不使用展开语法，保持响应式
    isConnecting: connection.isConnecting,
    isConnected: connection.isConnected,
    error: connection.error,
    reconnectAttempts: connection.reconnectAttempts,
    connect: connection.connect,
    disconnect: connection.disconnect,
    sendResearchRequest: connection.sendResearchRequest,
    // 管理器特有方法
    sendResearchRequestOnce,
    disconnectAndCleanup,
    hasRequestSent,
    resetRequestState,
  };
}

/**
 * 清理所有连接（应用关闭时使用）
 */
export function cleanupAllConnections() {
  console.log("[WebSocketManager] 清理所有连接");
  activeConnections.value.forEach((conn) => conn.disconnect());
  activeConnections.value.clear();
  requestSent.value.clear();
}
