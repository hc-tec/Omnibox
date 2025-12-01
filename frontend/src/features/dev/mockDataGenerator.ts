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
// ListPanel 热榜模式模拟数据
// ============================
export function generateHotListData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('hotlist');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 ListPanel 热榜模式模拟数据', { blockId, dataId });

  const records = [
    { title: '2024年诺贝尔物理学奖揭晓', link: 'https://example.com/hot/1', hot: 9876543 },
    { title: 'iPhone 16 Pro Max 首发评测', link: 'https://example.com/hot/2', hot: 8234567 },
    { title: '国庆假期出行人数创历史新高', link: 'https://example.com/hot/3', hot: 7654321 },
    { title: 'Claude 3.5 发布：性能全面超越GPT-4', link: 'https://example.com/hot/4', hot: 6543210 },
    { title: '比亚迪销量首次超越特斯拉', link: 'https://example.com/hot/5', hot: 5432109 },
    { title: '房贷利率再次下调', link: 'https://example.com/hot/6', hot: 4321098 },
    { title: '马斯克宣布火星计划最新进展', link: 'https://example.com/hot/7', hot: 3210987 },
    { title: 'A股市场迎来重大利好', link: 'https://example.com/hot/8', hot: 2109876 },
    { title: '教育部发布新规：减轻学生课业负担', link: 'https://example.com/hot/9', hot: 1098765 },
    { title: '新能源汽车补贴政策延长', link: 'https://example.com/hot/10', hot: 987654 },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'ListPanel',
    data_ref: dataId,
    title: '今日热榜',
    props: {
      title_field: 'title',
      link_field: 'link',
      hot_field: 'hot',
    },
    options: {
      variant: 'minimal',
      show_rank: true,
      max_items: 10,
      span: 6,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('weibo', '/hot/search'),
    records,
    stats: {
      item_count: records.length,
      description: '实时热搜榜单',
    },
    schema_summary: createSchemaSummary([
      { name: 'title', type: 'string' },
      { name: 'link', type: 'string' },
      { name: 'hot', type: 'number' },
    ]),
  };

  devLogger.debug('MockGenerator', 'ListPanel 热榜数据生成完成', { records: records.length });

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
      { name: 'link', type: 'string' },
      { name: 'description', type: 'string' },
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
      { name: 'link', type: 'string' },
      { name: 'description', type: 'string' },
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
    { url: 'https://picsum.photos/seed/1/400/300', title: '山间日出', description: '清晨的山峰被阳光染成金色' },
    { url: 'https://picsum.photos/seed/2/400/300', title: '城市夜景', description: '繁华都市的霓虹灯光' },
    { url: 'https://picsum.photos/seed/3/400/300', title: '海边落日', description: '温暖的夕阳洒在海面上' },
    { url: 'https://picsum.photos/seed/4/400/300', title: '森林小径', description: '幽静的林间步道' },
    { url: 'https://picsum.photos/seed/5/400/300', title: '雪山风光', description: '壮丽的雪山景色' },
    { url: 'https://picsum.photos/seed/6/400/300', title: '田园风光', description: '宁静的乡村田野' },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'ImageGallery',
    data_ref: dataId,
    title: '风景图集',
    props: {
      url_field: 'url',
      title_field: 'title',
      description_field: 'description',
    },
    options: {
      columns: 3,
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
      { name: 'url', type: 'string' },
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
// CountCard 模拟数据
// ============================
export function generateCountCardData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('count');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 CountCard 模拟数据', { blockId, dataId });

  const records = [
    {
      metric_title: '总播放量',
      metric_value: 12568423,
      unit: '次',
      description: '累计视频播放总量',
    },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'CountCard',
    data_ref: dataId,
    title: '播放统计',
    props: {
      title_field: 'metric_title',
      value_field: 'metric_value',
      unit_field: 'unit',
      description_field: 'description',
    },
    options: {
      color: 'primary',
      span: 4,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('analytics', '/stats/total'),
    records,
    stats: { item_count: 1, description: '单一数字指标展示' },
    schema_summary: createSchemaSummary([
      { name: 'metric_title', type: 'string' },
      { name: 'metric_value', type: 'number' },
      { name: 'unit', type: 'string' },
      { name: 'description', type: 'string' },
    ]),
  };

  return { block, dataBlock };
}

// ============================
// ProgressBar 模拟数据
// ============================
export function generateProgressBarData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('progress');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 ProgressBar 模拟数据', { blockId, dataId });

  const records = [
    {
      label: '任务完成度',
      value: 78,
      max: 100,
      description: '本周目标完成进度',
    },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'ProgressBar',
    data_ref: dataId,
    title: '进度追踪',
    props: {
      label_field: 'label',
      value_field: 'value',
      max_field: 'max',
      description_field: 'description',
    },
    options: {
      color: 'success',
      show_percentage: true,
      span: 6,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('tasks', '/progress'),
    records,
    stats: { item_count: 1, description: '进度条展示' },
    schema_summary: createSchemaSummary([
      { name: 'label', type: 'string' },
      { name: 'value', type: 'number' },
      { name: 'max', type: 'number' },
      { name: 'description', type: 'string' },
    ]),
  };

  return { block, dataBlock };
}

// ============================
// QuoteCard 模拟数据
// ============================
export function generateQuoteCardData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('quote');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 QuoteCard 模拟数据', { blockId, dataId });

  const records = [
    {
      content: '代码是写给人看的，只是顺便能在机器上运行。',
      author: 'Donald Knuth',
      source: '计算机程序设计艺术',
      timestamp: '1968-01-01T00:00:00Z',
    },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'QuoteCard',
    data_ref: dataId,
    title: '每日金句',
    props: {
      content_field: 'content',
      author_field: 'author',
      source_field: 'source',
      timestamp_field: 'timestamp',
    },
    options: {
      compact: false,
      span: 6,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('quotes', '/daily'),
    records,
    stats: { item_count: 1, description: '引用内容展示' },
    schema_summary: createSchemaSummary([
      { name: 'content', type: 'string' },
      { name: 'author', type: 'string' },
      { name: 'source', type: 'string' },
      { name: 'timestamp', type: 'datetime' },
    ]),
  };

  return { block, dataBlock };
}

// ============================
// ComparisonCard 模拟数据
// ============================
export function generateComparisonCardData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('comparison');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 ComparisonCard 模拟数据', { blockId, dataId });

  const records = [
    {
      left_label: '本月',
      left_value: 125680,
      left_unit: '元',
      right_label: '上月',
      right_value: 98540,
      right_unit: '元',
    },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'ComparisonCard',
    data_ref: dataId,
    title: '销售额对比',
    props: {
      left_label_field: 'left_label',
      left_value_field: 'left_value',
      left_unit_field: 'left_unit',
      right_label_field: 'right_label',
      right_value_field: 'right_value',
      right_unit_field: 'right_unit',
    },
    options: {
      show_diff: true,
      span: 6,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('sales', '/compare'),
    records,
    stats: { item_count: 1, description: '对比数据展示' },
    schema_summary: createSchemaSummary([
      { name: 'left_label', type: 'string' },
      { name: 'left_value', type: 'number' },
      { name: 'right_label', type: 'string' },
      { name: 'right_value', type: 'number' },
    ]),
  };

  return { block, dataBlock };
}

// ============================
// AuthorCard 模拟数据
// ============================
export function generateAuthorCardData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('author');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 AuthorCard 模拟数据', { blockId, dataId });

  const records = [
    {
      name: '科技美学',
      avatar: 'https://picsum.photos/seed/author1/100/100',
      bio: '分享科技产品评测，带你了解最新科技动态。专注数码领域10年。',
      verified: true,
      followers: 1256000,
      following: 128,
      posts: 892,
      link: 'https://space.bilibili.com/12345',
    },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'AuthorCard',
    data_ref: dataId,
    title: 'UP主信息',
    props: {
      name_field: 'name',
      avatar_field: 'avatar',
      bio_field: 'bio',
      verified_field: 'verified',
      followers_field: 'followers',
      following_field: 'following',
      posts_field: 'posts',
      link_field: 'link',
    },
    options: {
      span: 6,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('bilibili', '/user/info'),
    records,
    stats: { item_count: 1, description: '用户信息展示' },
    schema_summary: createSchemaSummary([
      { name: 'name', type: 'string' },
      { name: 'avatar', type: 'string' },
      { name: 'bio', type: 'string' },
      { name: 'verified', type: 'boolean' },
      { name: 'followers', type: 'number' },
      { name: 'posts', type: 'number' },
    ]),
  };

  return { block, dataBlock };
}

// ============================
// TagCloud 模拟数据
// ============================
export function generateTagCloudData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('tagcloud');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 TagCloud 模拟数据', { blockId, dataId });

  const records = [
    { name: 'JavaScript', count: 156 },
    { name: 'TypeScript', count: 128 },
    { name: 'Vue', count: 98 },
    { name: 'React', count: 87 },
    { name: 'Python', count: 76 },
    { name: 'Rust', count: 65 },
    { name: 'Go', count: 54 },
    { name: 'AI', count: 145 },
    { name: '前端', count: 112 },
    { name: '后端', count: 89 },
    { name: '云原生', count: 67 },
    { name: 'DevOps', count: 45 },
    { name: '数据库', count: 78 },
    { name: '微服务', count: 56 },
    { name: '区块链', count: 34 },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'TagCloud',
    data_ref: dataId,
    title: '热门标签',
    props: {
      name_field: 'name',
      count_field: 'count',
    },
    options: {
      max_tags: 15,
      show_count: false,
      span: 6,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('analytics', '/tags/hot'),
    records,
    stats: { item_count: records.length, description: '标签分布展示' },
    schema_summary: createSchemaSummary([
      { name: 'name', type: 'string' },
      { name: 'count', type: 'number' },
    ]),
  };

  return { block, dataBlock };
}

// ============================
// TimelineCard 模拟数据
// ============================
export function generateTimelineCardData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('timeline');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 TimelineCard 模拟数据', { blockId, dataId });

  const now = new Date();
  const records = [
    {
      id: '1',
      title: '发布新视频：2024年度科技盘点',
      timestamp: new Date(now.getTime() - 2 * 3600000).toISOString(),
      description: '回顾2024年最值得关注的科技产品和技术突破',
      status: 'completed',
      type: '视频',
      link: 'https://example.com/video/1',
    },
    {
      id: '2',
      title: '直播预告：新品开箱',
      timestamp: new Date(now.getTime() - 24 * 3600000).toISOString(),
      description: '明天晚上8点，一起来看新品开箱',
      status: 'pending',
      type: '直播',
      link: 'https://example.com/live/1',
    },
    {
      id: '3',
      title: '专栏文章更新',
      timestamp: new Date(now.getTime() - 48 * 3600000).toISOString(),
      description: '深度分析：AI对未来工作的影响',
      status: 'completed',
      type: '文章',
      link: 'https://example.com/article/1',
    },
    {
      id: '4',
      title: '获得10万粉丝里程碑',
      timestamp: new Date(now.getTime() - 72 * 3600000).toISOString(),
      description: '感谢大家的支持！',
      status: 'success',
      type: '里程碑',
    },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'TimelineCard',
    data_ref: dataId,
    title: '最近动态',
    props: {
      title_field: 'title',
      timestamp_field: 'timestamp',
      description_field: 'description',
      status_field: 'status',
      type_field: 'type',
      link_field: 'link',
    },
    options: {
      max_items: 10,
      show_description: true,
      span: 6,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('user', '/timeline'),
    records,
    stats: { item_count: records.length, description: '时间线事件展示' },
    schema_summary: createSchemaSummary([
      { name: 'title', type: 'string' },
      { name: 'timestamp', type: 'datetime' },
      { name: 'description', type: 'string' },
      { name: 'status', type: 'string' },
      { name: 'type', type: 'string' },
    ]),
  };

  return { block, dataBlock };
}

// ============================
// HeatmapCalendar 模拟数据
// ============================
export function generateHeatmapCalendarData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('heatmap');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 HeatmapCalendar 模拟数据', { blockId, dataId });

  // 生成过去90天的随机活动数据
  const records: { date: string; value: number }[] = [];
  const today = new Date();
  for (let i = 0; i < 90; i++) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    // 随机生成活动值，周末概率更高
    const dayOfWeek = date.getDay();
    const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
    const value = Math.random() > (isWeekend ? 0.3 : 0.5) ? Math.floor(Math.random() * 10) + 1 : 0;
    records.push({
      date: date.toISOString().split('T')[0],
      value,
    });
  }

  const block: UIBlock = {
    id: blockId,
    component: 'HeatmapCalendar',
    data_ref: dataId,
    title: '发布活跃度',
    props: {
      date_field: 'date',
      value_field: 'value',
    },
    options: {
      weeks: 13,
      show_stats: true,
      value_unit: '篇',
      span: 12,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('analytics', '/activity/calendar'),
    records,
    stats: { item_count: records.length, description: '活动热力图展示' },
    schema_summary: createSchemaSummary([
      { name: 'date', type: 'date' },
      { name: 'value', type: 'number' },
    ]),
  };

  return { block, dataBlock };
}

// ============================
// 边界情况测试数据
// ============================

// 各组件的必需 props 默认值
const EMPTY_DATA_PROPS: Record<string, Record<string, string>> = {
  ListPanel: { title_field: 'title', link_field: 'link' },
  LineChart: { x_field: 'x', y_field: 'y' },
  BarChart: { x_field: 'x', y_field: 'y' },
  PieChart: { name_field: 'name', value_field: 'value' },
  StatisticCard: { title_field: 'title', value_field: 'value' },
  ImageGallery: { url_field: 'url' },
  MediaCardGrid: { title_field: 'title' },
  Table: {},
  FallbackRichText: { title_field: 'title' },
  // 新增组件
  CountCard: { value_field: 'value' },
  ProgressBar: { value_field: 'value' },
  QuoteCard: { content_field: 'content' },
  ComparisonCard: { left_value_field: 'left_value', right_value_field: 'right_value' },
  AuthorCard: { name_field: 'name' },
  TagCloud: { name_field: 'name', count_field: 'count' },
  TimelineCard: { title_field: 'title', timestamp_field: 'timestamp' },
  HeatmapCalendar: { date_field: 'date', value_field: 'value' },
  ServiceStatus: { name_field: 'name', availability_field: 'availability_rate' },
};

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
    props: EMPTY_DATA_PROPS[component] ?? {},
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
    props: EMPTY_DATA_PROPS[component] ?? {},
    options: {
      show_description: true,
      span: 12,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('test', '/large-dataset'),
    records,
    stats: { item_count: count, description: `大量数据性能测试 (${count}条记录)` },
    schema_summary: createSchemaSummary([
      { name: 'id', type: 'number' },
      { name: 'title', type: 'string' },
      { name: 'link', type: 'string' },
      { name: 'description', type: 'string' },
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
    { title: '<script>alert("XSS")</script>', link: '#xss-test', description: 'XSS 注入测试' },
    { title: '包含\"引号\"和\'单引号\'', link: '#quotes-test', description: '引号转义测试' },
    { title: '特殊符号：&amp; &lt; &gt; &nbsp;', link: '#entities-test', description: 'HTML 实体测试' },
    { title: '超长文本测试：' + '这是一段很长的文字'.repeat(10), link: '#long-text', description: '超长文本截断测试' },
    { title: '中文、日本語、한국어、العربية', link: '#i18n-test', description: '多语言字符测试' },
    { title: '表情符号：😀🎉🚀💻🔥✨', link: '#emoji-test', description: 'Emoji 渲染测试' },
  ];

  const block: UIBlock = {
    id: blockId,
    component: 'ListPanel',
    data_ref: dataId,
    title: '特殊字符测试',
    props: {
      title_field: 'title',
      link_field: 'link',
      description_field: 'description',
    },
    options: {
      show_description: true,
      span: 12,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    source_info: createSourceInfo('test', '/special-chars'),
    records,
    stats: { item_count: records.length, description: '测试各种特殊字符的渲染' },
    schema_summary: createSchemaSummary([
      { name: 'title', type: 'string' },
      { name: 'link', type: 'string' },
      { name: 'description', type: 'string' },
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

// ServiceStatus 服务状态监控组件
export function generateServiceStatusData(): { block: UIBlock; dataBlock: DataBlock } {
  const blockId = generateId('service-status');
  const dataId = generateId('data');

  devLogger.info('MockGenerator', '生成 ServiceStatus 模拟数据', { blockId, dataId });

  // 生成24小时历史数据
  const history: { time: string; status: string }[] = [];
  for (let i = 0; i < 48; i++) {
    const rand = Math.random();
    let status = 'available';
    if (rand > 0.95) status = 'unavailable';
    else if (rand > 0.85) status = 'fluctuation';
    history.push({ time: `${23 - Math.floor(i / 2)}:${i % 2 === 0 ? '00' : '30'}`, status });
  }

  const records = [{
    name: 'VIP 数据服务',
    timestamp: new Date().toISOString(),
    availability_rate: 97.69,
    latency_ms: 2182,
    current_status: 'available',
    current_latency_ms: 1550,
    last_check_time: new Date().toISOString(),
    available_count: 12,
    fluctuation_count: 1,
    unavailable_count: 0,
    fluctuation_details: {
      slow_response: 1,
    },
    history,
  }];

  const block: UIBlock = {
    id: blockId,
    component: 'ServiceStatus',
    data_ref: dataId,
    title: '服务状态监控',
    props: {
      name_field: 'name',
      timestamp_field: 'timestamp',
      availability_field: 'availability_rate',
      latency_field: 'latency_ms',
      current_status_field: 'current_status',
      history_field: 'history',
    },
    options: {
      span: 6,
    },
  };

  const dataBlock: DataBlock = {
    id: dataId,
    records,
    stats: { total: 1 },
  };

  return { block, dataBlock };
}


export const allTestCases: ComponentTestCase[] = [
  {
    name: 'ListPanel - 标准',
    component: 'ListPanel',
    description: '标准列表展示，包含标题、描述、作者、日期等',
    generator: generateListPanelData,
  },
  {
    name: 'ListPanel - 热榜模式',
    component: 'ListPanel',
    description: '极简模式，适合热搜/排行榜，紧凑显示排名和标题',
    generator: generateHotListData,
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
  // 新增组件测试
  {
    name: 'CountCard - 标准',
    component: 'CountCard',
    description: '单一数字指标展示',
    generator: generateCountCardData,
  },
  {
    name: 'ProgressBar - 标准',
    component: 'ProgressBar',
    description: '进度条展示',
    generator: generateProgressBarData,
  },
  {
    name: 'QuoteCard - 标准',
    component: 'QuoteCard',
    description: '引用内容展示',
    generator: generateQuoteCardData,
  },
  {
    name: 'ComparisonCard - 标准',
    component: 'ComparisonCard',
    description: '对比数据展示',
    generator: generateComparisonCardData,
  },
  {
    name: 'AuthorCard - 标准',
    component: 'AuthorCard',
    description: '作者/账号信息展示',
    generator: generateAuthorCardData,
  },
  {
    name: 'TagCloud - 标准',
    component: 'TagCloud',
    description: '标签云展示',
    generator: generateTagCloudData,
  },
  {
    name: 'TimelineCard - 标准',
    component: 'TimelineCard',
    description: '时间线事件展示',
    generator: generateTimelineCardData,
  },
  {
    name: 'HeatmapCalendar - 标准',
    component: 'HeatmapCalendar',
    description: '活动热力图展示',
    generator: generateHeatmapCalendarData,
  },
  {
    id: 'service-status-standard',
    name: 'ServiceStatus 标准',
    component: 'ServiceStatus',
    category: 'monitor',
    generator: generateServiceStatusData,
  },
];
