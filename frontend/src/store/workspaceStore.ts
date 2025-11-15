/**
 * 统一工作区 Store
 * 管理所有查询卡片（普通查询 + 研究查询）
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { QueryCard, CardStatus, QueryMode, TriggerSource, RefreshMetadata } from '@/types/queryCard';
import type { UIBlock, PanelResponse, StreamMessage, PanelStreamFetchPayload } from '@/shared/types/panel';

export const useWorkspaceStore = defineStore('workspace', () => {
  // ========== 状态 ==========
  const cards = ref<QueryCard[]>([]);

  // ========== 计算属性 ==========

  /**
   * 获取所有卡片（按创建时间倒序）
   */
  const allCards = computed(() => {
    return [...cards.value].sort((a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  });

  /**
   * 获取工作区可见卡片（包括进行中和已完成的卡片）
   *
   * P1 修复：activeCards 现在返回所有应该在工作区显示的卡片，
   * 包括 pending、processing 和 completed 状态，
   * 按创建时间倒序排列，让用户可以看到查询历史并进行刷新。
   */
  const activeCards = computed(() => {
    return [...cards.value]
      .filter(card => card.status !== 'error')  // 过滤掉错误卡片
      .sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
  });

  /**
   * 获取进行中的卡片
   */
  const pendingCards = computed(() => {
    return cards.value.filter(card =>
      card.status === 'pending' || card.status === 'processing'
    );
  });

  /**
   * 获取已完成的卡片
   */
  const completedCards = computed(() => {
    return cards.value.filter(card => card.status === 'completed');
  });

  // ========== 方法 ==========

  /**
   * 添加新卡片
   */
  function addCard(card: QueryCard) {
    cards.value.push(card);
  }

  /**
   * 创建新卡片（快捷方法）
   */
  function createCard(params: {
    id: string;
    query: string;
    mode: QueryMode;
    trigger_source?: TriggerSource;
  }): QueryCard {
    const now = new Date().toISOString();
    const card: QueryCard = {
      id: params.id,
      query: params.query,
      mode: params.mode,
      status: 'pending',
      trigger_source: params.trigger_source || 'manual_input',
      created_at: now,
      updated_at: now,
      progress: 0,
    };

    addCard(card);
    return card;
  }

  /**
   * 更新卡片状态
   */
  function updateCardStatus(
    cardId: string,
    status: CardStatus,
    extraData?: {
      error_message?: string;
      current_step?: string;
      progress?: number;
    }
  ) {
    const card = getCard(cardId);
    if (!card) return;

    card.status = status;
    card.updated_at = new Date().toISOString();

    if (status === 'completed') {
      card.completed_at = card.updated_at;
    }

    if (extraData) {
      if (extraData.error_message !== undefined) {
        card.error_message = extraData.error_message;
      }
      if (extraData.current_step !== undefined) {
        card.current_step = extraData.current_step;
      }
      if (extraData.progress !== undefined) {
        card.progress = extraData.progress;
      }
    }
  }

  /**
   * 更新卡片进度
   */
  function updateCardProgress(cardId: string, progress: number, current_step?: string) {
    const card = getCard(cardId);
    if (!card) return;

    card.progress = progress;
    card.updated_at = new Date().toISOString();

    if (current_step) {
      card.current_step = current_step;
    }
  }

  /**
   * 更新卡片结果数据
   */
  function updateCardResult(
    cardId: string,
    panels: UIBlock[],
    refresh_metadata?: RefreshMetadata,
    inspectorData?: {
      metadata?: PanelResponse['metadata'];
      message?: string;
      streamLog?: StreamMessage[];
      fetchSnapshot?: PanelStreamFetchPayload | null;
    }
  ) {
    const card = getCard(cardId);
    if (!card) return;

    card.panels = panels;
    card.refresh_metadata = refresh_metadata;
    card.status = 'completed';
    card.completed_at = new Date().toISOString();
    card.updated_at = card.completed_at;
    card.progress = 100;

    // 保存 Inspector 调试信息
    if (inspectorData) {
      card.metadata = inspectorData.metadata;
      card.message = inspectorData.message;
      card.streamLog = inspectorData.streamLog;
      card.fetchSnapshot = inspectorData.fetchSnapshot;
    }
  }

  /**
   * 获取卡片
   */
  function getCard(cardId: string): QueryCard | undefined {
    return cards.value.find(card => card.id === cardId);
  }

  /**
   * 删除卡片
   */
  function deleteCard(cardId: string) {
    const index = cards.value.findIndex(card => card.id === cardId);
    if (index !== -1) {
      cards.value.splice(index, 1);
    }
  }

  /**
   * 清空所有已完成的卡片
   */
  function clearCompletedCards() {
    cards.value = cards.value.filter(card => card.status !== 'completed');
  }

  /**
   * 清空所有卡片
   */
  function clearAllCards() {
    cards.value = [];
  }

  /**
   * 搜索卡片（按查询文本）
   */
  function searchCards(keyword: string): QueryCard[] {
    if (!keyword.trim()) return allCards.value;

    const lowerKeyword = keyword.toLowerCase();
    return allCards.value.filter(card =>
      card.query.toLowerCase().includes(lowerKeyword)
    );
  }

  // ========== 导出 ==========
  return {
    // 状态
    cards,

    // 计算属性
    allCards,
    activeCards,
    completedCards,

    // 方法
    addCard,
    createCard,
    updateCardStatus,
    updateCardProgress,
    updateCardResult,
    getCard,
    deleteCard,
    clearCompletedCards,
    clearAllCards,
    searchCards,
  };
});
