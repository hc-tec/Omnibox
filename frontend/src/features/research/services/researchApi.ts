import axios from 'axios';
import type { QueryMode, ResearchResponse } from '../types/researchTypes';

const API_BASE = '/api/v1';

export const researchApi = {
  /**
   * 发起研究查询
   */
  async submitQuery(query: string, mode: QueryMode): Promise<ResearchResponse> {
    const response = await axios.post<ResearchResponse>(`${API_BASE}/chat`, {
      query,
      mode,
    });
    return response.data;
  },

  /**
   * 提交人工响应
   */
  async submitHumanResponse(taskId: string, response: string): Promise<void> {
    await axios.post(`${API_BASE}/research/human-response`, {
      task_id: taskId,
      response,
    });
  },

  /**
   * 取消研究任务
   */
  async cancelTask(taskId: string): Promise<void> {
    await axios.post(`${API_BASE}/research/cancel`, {
      task_id: taskId,
    });
  },
};
