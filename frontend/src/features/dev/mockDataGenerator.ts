/**
 * 开发者调试页面 - 模拟数据生成器
 *
 * 为各种面板组件生成标准化的模拟数据，用于调试和验证组件渲染。
 */

import type { UIBlock, DataBlock, SourceInfo, SchemaSummary } from '@/shared/types/panel';

// 日志级别
export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

// 日志条目
export interface LogEntry {
  id: string;
  timestamp: Date;
  level: LogLevel;
  component: string;
  message: string;
  data?: unknown;
}

// 日志管理器
class DevLogger {
  private logs: LogEntry[] = [];
  private listeners: ((logs: LogEntry[]) => void)[] = [];
  private maxLogs = 500;

  log(level: LogLevel, component: string, message: string, data?: unknown) {
    const entry: LogEntry = {
      id: `log-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      level,
      component,
      message,
      data,
    };

    this.logs.unshift(entry);
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(0, this.maxLogs);
    }

    // 同时输出到控制台
    const consoleMethod = level === 'error' ? 'error' : level === 'warn' ? 'warn' : 'log';
    console[consoleMethod](`[${component}] ${message}`, data ?? '');

    this.notifyListeners();
  }

  debug(component: string, message: string, data?: unknown) {
    this.log('debug', component, message, data);
  }

  info(component: string, message: string, data?: unknown) {
    this.log('info', component, message, data);
  }

  warn(component: string, message: string, data?: unknown) {
    this.log('warn', component, message, data);
  }

  error(component: string, message: string, data?: unknown) {
    this.log('error', component, message, data);
  }

  getLogs(): LogEntry[] {
    return [...this.logs];
  }

  clear() {
    this.logs = [];
    this.notifyListeners();
  }

  subscribe(listener: (logs: LogEntry[]) => void) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  private notifyListeners() {
    this.listeners.forEach((l) => l(this.getLogs()));
  }
}

// 全局日志实例
export const devLogger = new DevLogger();

// 生成唯一 ID
function generateId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

// 基础 SourceInfo
function createSourceInfo(datasource: string, route: string): SourceInfo {
  return {
    datasource,
    route,
    params: {},
    fetched_at: new Date().toISOString(),
    request_id: generateId('req'),
  };
}

// 基础 SchemaSummary
function createSchemaSummary(fields: { name: string; type: string }[]): SchemaSummary {
  return {
    fields: fields.map((f) => ({
      name: f.name,
      type: f.type,
      sample: [],
    })),
    stats: { record_count: 0 },
    schema_digest: generateId('schema'),
  };
}

// ============================
// ListPanel 模拟数据
// ============================
export function generateListPanelData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('list');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 ListPanel 模拟数据', { blockId, dataId });

  const records = [
    {
      title: '如何评价 2024 年科技发展趋势？',
      description: '2024年AI领域迎来爆发式增长，GPT-5、Claude 3等模型相继发布...',
      link: 'https://example.com/article/1',
      pubDate: '2024-03-15T10:30:00Z',
      author: '科技观察者',
      categories: ['科技', 'AI', '年度盘点'],
    },
    {
      title: 'Vue 3.4 正式发布：性能提升与新特性解读',
      description: 'Vue 3.4 带来了显著的性能优化，包括响应式系统重构...',
      link: 'https://example.com/article/2',
      pubDate: '2024-03-14T08:15:00Z',
      author: '前端技术周刊',
      categories: ['前端', 'Vue', '技术'],
    },
    {
      title: '深度解析：TypeScript 5.4 新特性一览',
      description: '本次更新带来了更强大的类型推断能力和新的工具类型...',
      link: 'https://example.com/article/3',
      pubDate: '2024-03-13T14:20:00Z',
      author: 'TS爱好者',
      categories: ['前端', 'TypeScript'],
    },
    {
      title: 'Rust 在后端开发中的实践经验分享',
      description: '从 Go 迁移到 Rust，我们的服务性能提升了 40%...',
      link: 'https://example.com/article/4',
      pubDate: '2024-03-12T16:45:00Z',
      author: '后端架构师',
      categories: ['后端', 'Rust', '性能优化'],
    },
    {
      title: '2024年最值得关注的10个开源项目',
      description: '从基础设施到应用层，这些开源项目正在改变开发者的工作方式...',
      link: 'https://example.com/article/5',
      pubDate: '2024-03-11T09:00:00Z',
      author: '开源中国',
      categories: ['开源', '推荐'],
    },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'ListPanel',
    data_ref: dataId,
    title: '技术资讯列表',
    props: {
      title_field: 'title',
      link_field: 'link',
      description_field: 'description',
      pub_date_field: 'pubDate',
      author_field: 'author',
      categories_field: 'categories',
    },
    options: {
      show_description: true,
      show_metadata: true,
      show_categories: true,
      max_items: 10,
      compact: false,
      span: 12,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('rsshub', '/zhihu/hot'),
    records,
    stats: {
      item_count: records.length,
      description: '最新技术资讯，来自多个技术社区',
    },
    schema_summary: createSchemaSummary([
      { name: 'title', type: 'string' },
      { name: 'description', type: 'string' },
      { name: 'link', type: 'string' },
      { name: 'pubDate', type: 'datetime' },
      { name: 'author', type: 'string' },
      { name: 'categories', type: 'array' },
    ]),
  };

  devLogger.debug('MockGenerator', 'ListPanel 数据生成完成', { records: records.length });

  return { block, dataBlock };
}

// ============================
// StatisticCard 模拟数据
// ============================
export function generateStatisticCardData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('stat');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 StatisticCard 模拟数据', { blockId, dataId });

  // StatisticCardBlock 期望从 records[0] 读取数据
  // 字段名约定: metric_title, metric_value, metric_unit, metric_trend, metric_delta_text
  const records = [
    {
      metric_title: '日活用户',
      metric_value: 128543,
      metric_unit: '人',
      metric_trend: 'up',
      metric_delta_text: '+12.5% 较昨日',
      description: '今日活跃用户数量统计',
    },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'StatisticCard',
    data_ref: dataId,
    title: '用户活跃指标',
    props: {
      title_field: 'metric_title',
      value_field: 'metric_value',
      trend_field: 'metric_trend',
    },
    options: {
      span: 3,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('analytics', '/metrics/daily'),
    records,
    stats: {
      item_count: records.length,
      description: '今日实时数据统计',
    },
    schema_summary: createSchemaSummary([
      { name: 'metric_title', type: 'string' },
      { name: 'metric_value', type: 'number' },
      { name: 'metric_unit', type: 'string' },
      { name: 'metric_trend', type: 'string' },
      { name: 'metric_delta_text', type: 'string' },
      { name: 'description', type: 'string' },
    ]),
  };

  devLogger.debug('MockGenerator', 'StatisticCard 数据生成完成', { records: records.length });

  return { block, dataBlock };
}

// ============================
// LineChart 模拟数据
// ============================
export function generateLineChartData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('line');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 LineChart 模拟数据', { blockId, dataId });

  // 生成过去7天的数据
  const records: Record<string, unknown>[] = [];
  const today = new Date();

  for (let i = 6; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    const dateStr = date.toISOString().split('T')[0];

    records.push({
      x: dateStr,
      y: Math.floor(Math.random() * 5000) + 3000,
      series: '页面访问',
    });
    records.push({
      x: dateStr,
      y: Math.floor(Math.random() * 2000) + 1000,
      series: '独立用户',
    });
  }

  const block: UIBlock = {
    id: blockId,
    component: 'LineChart',
    data_ref: dataId,
    title: '访问趋势图',
    props: {
      x_field: 'x',
      y_field: 'y',
      series_field: 'series',
    },
    options: {
      smooth: true,
      areaStyle: false,
      span: 6,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('analytics', '/traffic/daily'),
    records,
    stats: {
      item_count: records.length,
      description: '过去7天访问趋势',
    },
    schema_summary: createSchemaSummary([
      { name: 'x', type: 'date' },
      { name: 'y', type: 'number' },
      { name: 'series', type: 'string' },
    ]),
  };

  devLogger.debug('MockGenerator', 'LineChart 数据生成完成', { records: records.length });

  return { block, dataBlock };
}

// ============================
// BarChart 模拟数据
// ============================
export function generateBarChartData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('bar');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 BarChart 模拟数据', { blockId, dataId });

  const records = [
    { category: '电子产品', value: 45000, series: '2023' },
    { category: '电子产品', value: 52000, series: '2024' },
    { category: '服装配饰', value: 32000, series: '2023' },
    { category: '服装配饰', value: 38000, series: '2024' },
    { category: '食品饮料', value: 28000, series: '2023' },
    { category: '食品饮料', value: 31000, series: '2024' },
    { category: '家居用品', value: 18000, series: '2023' },
    { category: '家居用品', value: 22000, series: '2024' },
    { category: '运动户外', value: 15000, series: '2023' },
    { category: '运动户外', value: 19000, series: '2024' },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'BarChart',
    data_ref: dataId,
    title: '品类销售对比',
    props: {
      x_field: 'category',
      y_field: 'value',
      series_field: 'series',
    },
    options: {
      horizontal: false,
      stacked: false,
      span: 6,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('sales', '/category/compare'),
    records,
    stats: {
      item_count: records.length,
      description: '各品类年度销售额对比（单位：元）',
    },
    schema_summary: createSchemaSummary([
      { name: 'category', type: 'string' },
      { name: 'value', type: 'number' },
      { name: 'series', type: 'string' },
    ]),
  };

  devLogger.debug('MockGenerator', 'BarChart 数据生成完成', { records: records.length });

  return { block, dataBlock };
}

// ============================
// PieChart 模拟数据
// ============================
export function generatePieChartData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('pie');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 PieChart 模拟数据', { blockId, dataId });

  const records = [
    { name: '直接访问', value: 335 },
    { name: '搜索引擎', value: 1548 },
    { name: '社交媒体', value: 310 },
    { name: '外部链接', value: 234 },
    { name: '邮件营销', value: 135 },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'PieChart',
    data_ref: dataId,
    title: '流量来源分布',
    props: {
      name_field: 'name',
      value_field: 'value',
    },
    options: {
      roseType: false,
      radius: '60%',
      showLabel: true,
      span: 6,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('analytics', '/traffic/source'),
    records,
    stats: {
      item_count: records.length,
      description: '网站流量来源占比分析',
    },
    schema_summary: createSchemaSummary([
      { name: 'name', type: 'string' },
      { name: 'value', type: 'number' },
    ]),
  };

  devLogger.debug('MockGenerator', 'PieChart 数据生成完成', { records: records.length });

  return { block, dataBlock };
}

// ============================
// Table 模拟数据
// ============================
export function generateTableData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('table');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 Table 模拟数据', { blockId, dataId });

  const records = [
    { id: 1, name: '张三', department: '技术部', position: '高级工程师', salary: 25000, joinDate: '2021-03-15' },
    { id: 2, name: '李四', department: '产品部', position: '产品经理', salary: 22000, joinDate: '2020-07-20' },
    { id: 3, name: '王五', department: '设计部', position: 'UI设计师', salary: 18000, joinDate: '2022-01-10' },
    { id: 4, name: '赵六', department: '技术部', position: '前端工程师', salary: 20000, joinDate: '2021-09-05' },
    { id: 5, name: '钱七', department: '运营部', position: '运营专员', salary: 12000, joinDate: '2023-02-28' },
    { id: 6, name: '孙八', department: '技术部', position: '后端工程师', salary: 23000, joinDate: '2020-11-15' },
    { id: 7, name: '周九', department: '市场部', position: '市场经理', salary: 21000, joinDate: '2019-06-01' },
    { id: 8, name: '吴十', department: '人事部', position: 'HR专员', salary: 14000, joinDate: '2022-08-20' },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'Table',
    data_ref: dataId,
    title: '员工信息表',
    props: {
      columns: [
        { field: 'id', header: 'ID', width: '60px' },
        { field: 'name', header: '姓名', width: '80px' },
        { field: 'department', header: '部门', width: '100px' },
        { field: 'position', header: '职位', width: '120px' },
        { field: 'salary', header: '薪资', width: '100px' },
        { field: 'joinDate', header: '入职日期', width: '120px' },
      ],
    },
    options: {
      enable_pagination: true,
      page_size: 5,
      enable_sorting: true,
      span: 12,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('hr', '/employees/list'),
    records,
    stats: {
      item_count: records.length,
      description: '公司员工基本信息列表',
    },
    schema_summary: createSchemaSummary([
      { name: 'id', type: 'number' },
      { name: 'name', type: 'string' },
      { name: 'department', type: 'string' },
      { name: 'position', type: 'string' },
      { name: 'salary', type: 'number' },
      { name: 'joinDate', type: 'date' },
    ]),
  };

  devLogger.debug('MockGenerator', 'Table 数据生成完成', { records: records.length });

  return { block, dataBlock };
}

// ============================
// ImageGallery 模拟数据
// ============================
export function generateImageGalleryData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('gallery');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 ImageGallery 模拟数据', { blockId, dataId });

  // 使用 picsum.photos 作为占位图
  const records = [
    { imageUrl: 'https://picsum.photos/seed/1/400/300', title: '山间日出', description: '清晨的山峰被阳光染成金色' },
    { imageUrl: 'https://picsum.photos/seed/2/400/300', title: '城市夜景', description: '繁华都市的霓虹灯光' },
    { imageUrl: 'https://picsum.photos/seed/3/400/300', title: '海边落日', description: '温暖的夕阳洒在海面上' },
    { imageUrl: 'https://picsum.photos/seed/4/400/300', title: '森林小径', description: '幽静的林间步道' },
    { imageUrl: 'https://picsum.photos/seed/5/400/300', title: '雪山风光', description: '壮丽的雪山景色' },
    { imageUrl: 'https://picsum.photos/seed/6/400/300', title: '田园风光', description: '宁静的乡村田野' },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'ImageGallery',
    data_ref: dataId,
    title: '风景图集',
    props: {
      image_field: 'imageUrl',
      title_field: 'title',
      description_field: 'description',
    },
    options: {
      columns: 3,
      aspect_ratio: '4/3',
      show_title: true,
      span: 12,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('gallery', '/photos/nature'),
    records,
    stats: {
      item_count: records.length,
      description: '自然风景摄影作品集',
    },
    schema_summary: createSchemaSummary([
      { name: 'imageUrl', type: 'string' },
      { name: 'title', type: 'string' },
      { name: 'description', type: 'string' },
    ]),
  };

  devLogger.debug('MockGenerator', 'ImageGallery 数据生成完成', { records: records.length });

  return { block, dataBlock };
}

// ============================
// MediaCardGrid 模拟数据
// ============================
export function generateMediaCardGridData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('media');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 MediaCardGrid 模拟数据', { blockId, dataId });

  const records = [
    {
      title: '【4K】2024年度科技产品盘点',
      cover: 'https://picsum.photos/seed/v1/320/180',
      author: '科技美学',
      views: 1256000,
      duration: '15:32',
      pubDate: '2024-03-10T18:00:00Z',
      link: 'https://example.com/video/1',
    },
    {
      title: 'MacBook Pro M3 深度体验：值得升级吗？',
      cover: 'https://picsum.photos/seed/v2/320/180',
      author: '大狸子切切里',
      views: 892000,
      duration: '22:45',
      pubDate: '2024-03-09T12:30:00Z',
      link: 'https://example.com/video/2',
    },
    {
      title: 'Vision Pro 一个月使用报告',
      cover: 'https://picsum.photos/seed/v3/320/180',
      author: '影视飓风',
      views: 2340000,
      duration: '18:20',
      pubDate: '2024-03-08T20:00:00Z',
      link: 'https://example.com/video/3',
    },
    {
      title: '程序员的一天 Vlog',
      cover: 'https://picsum.photos/seed/v4/320/180',
      author: '码农日记',
      views: 156000,
      duration: '10:15',
      pubDate: '2024-03-07T09:00:00Z',
      link: 'https://example.com/video/4',
    },
    {
      title: 'AI 绘画入门教程',
      cover: 'https://picsum.photos/seed/v5/320/180',
      author: 'AI创作者',
      views: 478000,
      duration: '28:30',
      pubDate: '2024-03-06T15:00:00Z',
      link: 'https://example.com/video/5',
    },
    {
      title: '2024 最值得入手的耳机推荐',
      cover: 'https://picsum.photos/seed/v6/320/180',
      author: '音频研究所',
      views: 623000,
      duration: '20:10',
      pubDate: '2024-03-05T14:00:00Z',
      link: 'https://example.com/video/6',
    },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'MediaCardGrid',
    data_ref: dataId,
    title: '热门视频推荐',
    props: {
      title_field: 'title',
      cover_field: 'cover',
      author_field: 'author',
      view_count_field: 'views',
      duration_field: 'duration',
      link_field: 'link',
    },
    options: {
      columns: 3,
      max_items: 6,
      span: 12,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('bilibili', '/popular/videos'),
    records,
    stats: {
      item_count: records.length,
      description: 'B站热门科技视频精选',
    },
    schema_summary: createSchemaSummary([
      { name: 'title', type: 'string' },
      { name: 'cover', type: 'string' },
      { name: 'author', type: 'string' },
      { name: 'views', type: 'number' },
      { name: 'duration', type: 'string' },
      { name: 'pubDate', type: 'datetime' },
      { name: 'link', type: 'string' },
    ]),
  };

  devLogger.debug('MockGenerator', 'MediaCardGrid 数据生成完成', { records: records.length });

  return { block, dataBlock };
}

// ============================
// 边界情况测试数据
// ============================

// 空数据测试
export function generateEmptyData(component: string): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('empty');
  const dataId = generateId('data');

  devLogger.warn('MockGenerator', `生成空数据测试: ${component}`, { blockId });

  const block: UIBlock = {
    id: blockId,
    component,
    data_ref: dataId,
    title: `${component} - 空数据测试`,
    props: {},
    options: { span: 6 },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('test', '/empty'),
    records: [],
    stats: { item_count: 0, description: '空数据测试场景' },
    schema_summary: createSchemaSummary([]),
  };

  return { block, dataBlock };
}

// 大量数据测试
export function generateLargeDataset(component: string, count: number): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('large');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', `生成大量数据测试: ${component}`, { blockId, count });

  const records: Record<string, unknown>[] = [];
  for (let i = 0; i < count; i++) {
    records.push({
      id: i + 1,
      title: `测试数据项 #${i + 1}`,
      value: Math.floor(Math.random() * 10000),
      category: `分类${(i % 5) + 1}`,
      date: new Date(Date.now() - i * 86400000).toISOString(),
    });
  }

  const block: UIBlock = {
    id: blockId,
    component,
    data_ref: dataId,
    title: `${component} - 大量数据测试 (${count}条)`,
    props: {},
    options: { span: 12 },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('test', '/large-dataset'),
    records,
    stats: { item_count: count, description: `大量数据性能测试 (${count}条记录)` },
    schema_summary: createSchemaSummary([
      { name: 'id', type: 'number' },
      { name: 'title', type: 'string' },
      { name: 'value', type: 'number' },
      { name: 'category', type: 'string' },
      { name: 'date', type: 'datetime' },
    ]),
  };

  return { block, dataBlock };
}

// 特殊字符测试
export function generateSpecialCharsData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('special');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成特殊字符测试数据', { blockId });

  const records = [
    { title: '<script>alert("XSS")</script>', value: 100 },
    { title: '包含"引号"和\'单引号\'', value: 200 },
    { title: '特殊符号：&amp; &lt; &gt; &nbsp;', value: 300 },
    { title: '超长文本'.repeat(50), value: 400 },
    { title: '中文、日本語、한국어、العربية', value: 500 },
    { title: '表情符号：😀🎉🚀💻', value: 600 },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'ListPanel',
    data_ref: dataId,
    title: '特殊字符测试',
    props: {
      titleField: 'title',
    },
    options: { span: 12 },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('test', '/special-chars'),
    records,
    stats: { item_count: records.length, description: '测试各种特殊字符的渲染' },
    schema_summary: createSchemaSummary([
      { name: 'title', type: 'string' },
      { name: 'value', type: 'number' },
    ]),
  };

  return { block, dataBlock };
}

// 汇总：生成所有组件的测试数据
export interface ComponentTestCase {
  name: string;
  component: string;
  description: string;
  generator: () => { block: UIBlock; dataBlock: DataBlock };
}

export const allTestCases: ComponentTestCase[] = [
  {
    name: 'ListPanel - 标准',
    component: 'ListPanel',
    description: '标准列表展示，包含标题、描述、作者、日期等',
    generator: generateListPanelData,
  },
  {
    name: 'StatisticCard - 标准',
    component: 'StatisticCard',
    description: '指标卡片，展示多个数值指标及趋势',
    generator: generateStatisticCardData,
  },
  {
    name: 'LineChart - 标准',
    component: 'LineChart',
    description: '折线图，展示时间序列数据趋势',
    generator: generateLineChartData,
  },
  {
    name: 'BarChart - 标准',
    component: 'BarChart',
    description: '柱状图，展示分类数据对比',
    generator: generateBarChartData,
  },
  {
    name: 'PieChart - 标准',
    component: 'PieChart',
    description: '饼图，展示占比分布',
    generator: generatePieChartData,
  },
  {
    name: 'Table - 标准',
    component: 'Table',
    description: '数据表格，支持分页和排序',
    generator: generateTableData,
  },
  {
    name: 'ImageGallery - 标准',
    component: 'ImageGallery',
    description: '图片画廊，网格展示图片',
    generator: generateImageGalleryData,
  },
  {
    name: 'MediaCardGrid - 标准',
    component: 'MediaCardGrid',
    description: '媒体卡片网格，展示视频/文章卡片',
    generator: generateMediaCardGridData,
  },
  {
    name: 'ListPanel - 空数据',
    component: 'ListPanel',
    description: '测试空数据时的展示效果',
    generator: () => generateEmptyData('ListPanel'),
  },
  {
    name: 'LineChart - 空数据',
    component: 'LineChart',
    description: '测试图表在无数据时的展示',
    generator: () => generateEmptyData('LineChart'),
  },
  {
    name: 'BarChart - 空数据',
    component: 'BarChart',
    description: '测试柱状图在无数据时的展示',
    generator: () => generateEmptyData('BarChart'),
  },
  {
    name: 'PieChart - 空数据',
    component: 'PieChart',
    description: '测试饼图在无数据时的展示',
    generator: () => generateEmptyData('PieChart'),
  },
  {
    name: 'Table - 大量数据',
    component: 'Table',
    description: '测试表格在大量数据时的性能',
    generator: () => generateLargeDataset('Table', 100),
  },
  {
    name: 'ListPanel - 特殊字符',
    component: 'ListPanel',
    description: '测试特殊字符、XSS、超长文本等边界情况',
    generator: generateSpecialCharsData,
  },
];
