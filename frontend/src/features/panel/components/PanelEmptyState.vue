<template>
  <div class="empty-state">
    <h3>欢迎使用智能数据面板</h3>
    <p>请输入查询内容或通过 WebSocket 观察流式状态，渲染结果将出现在此处。</p>
    <ul>
      <li>默认查询示例：<code>虎扑步行街最新帖子</code></li>
      <li>支持 <strong>append / replace</strong> 等布局模式</li>
      <li>右侧“流式进度”会实时展示后端返回过程</li>
    </ul>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.empty-state {
  border: 1px dashed rgba(148, 163, 184, 0.6);
  border-radius: 12px;
  padding: 36px;
  text-align: center;
  color: #475569;
  background: rgba(241, 245, 249, 0.6);
  margin-top: 12px;
}

code {
  background: rgba(15, 23, 42, 0.08);
  color: #0f172a;
  padding: 2px 6px;
  border-radius: 6px;
}

ul {
  margin: 16px auto 0;
  max-width: 420px;
  text-align: left;
  padding-left: 18px;
}
</style>
