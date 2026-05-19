import { Button, Empty, Input, Popconfirm, Select, Space, Table, Tag, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { AlertTriangle, ClipboardList, FileClock, Search, SquarePen, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { retryHistoryParse } from '../../api/bidProject';
import { CategoryList } from '../../components/common/CategoryList';
import { MetricCards } from '../../components/common/MetricCards';
import { ModuleHeader } from '../../components/common/ModuleHeader';

interface HistoryItem {
  id: string;
  project_name?: string | null;
  project_no?: string | null;
  tender_unit?: string | null;
  agency?: string | null;
  project_type?: string | null;
  status?: string | null;
  stage?: string;
  action?: string;
  analysis_count?: number;
  requirement_count?: number;
  risk_count?: number;
  section_count?: number;
  chunk_count?: number;
  file_count?: number;
  parse_status?: string | null;
  latest_file_id?: string | null;
  parse_task_id?: string | null;
  parse_error?: string | null;
  parse_raw_error?: string | null;
  parse_retryable?: boolean;
  parse_failure_stage?: string | null;
  parse_error_type?: string | null;
  parse_download_retry_count?: number;
  parse_updated_at?: string | null;
  latest_file_name?: string | null;
  created_at?: string | null;
}

const stageColor: Record<string, string> = {
  已上传: 'cyan',
  解析完成: 'purple',
  解析中: 'processing',
  解析失败: 'red',
  解读完成: 'blue',
  标书编制: 'green',
  failed: 'red',
};

const parseStatusLabel: Record<string, string> = {
  indexed: '解析完成',
  uploaded: '已上传',
  pending: '等待解析',
  parsing: '解析中',
  syncing_supabase: '同步文件中',
  supabase_synced: '等待解析',
  mineru_submitted: 'MinerU解析中',
  mineru_running: 'MinerU解析中',
  mineru_split_submitted: '大文件分片解析',
  mineru_split_running: '大文件分片解析',
  mineru_downloading: '下载解析结果',
  mineru_download_retrying: '下载重试中',
  mineru_importing_zip: '导入解析结果',
  mineru_fallback_native: '原生抽取兜底',
  mineru_done: 'MinerU完成',
  mineru_failed: 'MinerU失败',
  mineru_download_failed: '结果下载失败',
  mineru_import_failed: '结果导入失败',
  supabase_sync_failed: '文件同步失败',
  ocr_required: '需要OCR',
  failed: '解析失败',
};

const runningParseStatuses = new Set([
  'uploaded',
  'pending',
  'parsing',
  'syncing_supabase',
  'supabase_synced',
  'mineru_submitted',
  'mineru_running',
  'mineru_split_submitted',
  'mineru_split_running',
  'mineru_downloading',
  'mineru_download_retrying',
  'mineru_importing_zip',
  'mineru_fallback_native',
]);

const failedParseStatuses = new Set([
  'failed',
  'mineru_failed',
  'index_failed',
  'ocr_required',
  'mineru_download_failed',
  'mineru_import_failed',
  'supabase_sync_failed',
]);

const ACTIVE_WORKFLOW_KEY = 'aiBiddingActiveWorkflow';

function formatDate(value?: string | null): string {
  if (!value) return '-';
  return new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

export function HistoryPage(): JSX.Element {
  const navigate = useNavigate();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState('全部记录');
  const [keyword, setKeyword] = useState('');

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const { data } = await apiClient.get<{ items: HistoryItem[] }>('/api/bidding/history', {
        skipGlobalLoading: true,
      });
      setItems(data.items || []);
    } catch (error: any) {
      message.error(error.message || '获取历史记录失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  useEffect(() => {
    const hasRunningTask = items.some(item => item.stage === '解析中' || runningParseStatuses.has(item.parse_status || ''));
    if (!hasRunningTask) return undefined;
    const timer = window.setInterval(() => {
      void fetchHistory();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [items]);

  const stageCategories = useMemo(() => {
    const counts = items.reduce<Record<string, number>>((acc, item) => {
      const stage = item.stage || '已上传';
      acc[stage] = (acc[stage] || 0) + 1;
      return acc;
    }, {});
    const order = ['解析中', '解析失败', '已上传', '解析完成', '解读完成', '标书编制'];
    return [
      { name: '全部记录', count: items.length },
      ...order.filter(stage => counts[stage]).map(stage => ({ name: stage, count: counts[stage] })),
      ...Object.keys(counts).filter(stage => !order.includes(stage)).map(stage => ({ name: stage, count: counts[stage] })),
    ];
  }, [items]);

  const filteredItems = useMemo(() => {
    const lowered = keyword.trim().toLowerCase();
    return items.filter(item => {
      const stageMatched = activeStage === '全部记录' || item.stage === activeStage;
      const keywordMatched = !lowered || [
        item.project_name,
        item.project_no,
        item.tender_unit,
        item.agency,
        item.project_type,
      ].some(value => (value || '').toLowerCase().includes(lowered));
      return stageMatched && keywordMatched;
    });
  }, [activeStage, items, keyword]);

  const openRecord = (record: HistoryItem) => {
    if (!record.id) return;
    if ((record.section_count || 0) > 0 || record.stage === '标书编制') {
      window.location.href = `/bid-editor?projectId=${record.id}`;
      return;
    }
    navigate(`/interpretation?projectId=${record.id}`);
  };

  const deleteRecord = async (record: HistoryItem) => {
    try {
      await apiClient.delete(`/api/bidding/history/${record.id}`, { skipGlobalLoading: true });
      message.success('历史任务已删除');
      await fetchHistory();
    } catch (error: any) {
      message.error(error.message || '删除历史任务失败');
    }
  };

  const retryParse = async (record: HistoryItem) => {
    try {
      setRetryingId(record.id);
      const result = await retryHistoryParse(record.id);
      localStorage.setItem(ACTIVE_WORKFLOW_KEY, JSON.stringify({
        fileName: record.latest_file_name || record.project_name || '历史解析任务',
        fileId: result.fileId,
        projectId: record.id,
        startedAt: Date.now(),
      }));
      message.success('解析重试任务已启动，首页流程和历史记录会继续跟踪状态');
      await fetchHistory();
    } catch (error: any) {
      message.error(error.message || '重试解析失败');
    } finally {
      setRetryingId(null);
    }
  };

  const columns: ColumnsType<HistoryItem> = [
    {
      title: '任务信息',
      dataIndex: 'project_name',
      width: 380,
      render: (value, record) => (
        <div className="min-w-0 pr-2">
          <div className="truncate text-sm font-black text-slate-950" title={value || '未命名招标项目'}>
            {value || '未命名招标项目'}
          </div>
          {record.latest_file_name ? (
            <div className="mt-1 truncate text-xs font-semibold text-slate-500" title={record.latest_file_name}>
              文件：{record.latest_file_name}
            </div>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            <Tag>编号 {record.project_no || '-'}</Tag>
            <Tag>类型 {record.project_type || '-'}</Tag>
            {record.tender_unit ? <Tag>招标单位 {record.tender_unit}</Tag> : null}
          </div>
        </div>
      ),
    },
    {
      title: '处理状态',
      width: 220,
      render: (_, record) => {
        const parseStatus = record.parse_status || '';
        const failed = failedParseStatuses.has(parseStatus) || record.stage === '解析失败';
        return (
          <div className="flex flex-col items-start gap-2">
            <Tag color={stageColor[record.stage || '已上传'] || 'default'}>{record.stage || '已上传'}</Tag>
            <Tag color={failed ? 'red' : runningParseStatuses.has(parseStatus) ? 'processing' : 'default'}>
              {parseStatusLabel[parseStatus] || parseStatus || '-'}
            </Tag>
            {record.parse_error ? (
              <div className="line-clamp-2 max-w-[200px] text-xs font-semibold text-red-500" title={record.parse_error}>
                原因：{record.parse_error}
              </div>
            ) : null}
            {record.parse_failure_stage || record.parse_download_retry_count ? (
              <div className="text-[11px] font-semibold text-slate-400">
                {record.parse_failure_stage ? `阶段 ${record.parse_failure_stage}` : ''}
                {record.parse_download_retry_count ? ` · 下载重试 ${record.parse_download_retry_count} 次` : ''}
              </div>
            ) : null}
            {record.parse_task_id ? (
              <div className="text-[11px] font-semibold text-slate-400">任务 {record.parse_task_id.slice(0, 8)}</div>
            ) : null}
          </div>
        );
      },
    },
    {
      title: '解析摘要',
      width: 210,
      render: (_, record) => (
        <Space size={[4, 6]} wrap>
          <Tag>需求 {record.requirement_count || 0}</Tag>
          <Tag>风险 {record.risk_count || 0}</Tag>
          <Tag>章节 {record.section_count || 0}</Tag>
          {record.file_count ? <Tag>文件 {record.file_count}</Tag> : null}
        </Space>
      ),
    },
    { title: '创建时间', dataIndex: 'created_at', width: 155, render: value => <span className="text-slate-600">{formatDate(value)}</span> },
    {
      title: '操作',
      width: 160,
      align: 'right',
      render: (_, record) => (
        <Space size={6}>
          {(record.parse_retryable || record.stage === '解析失败' || failedParseStatuses.has(record.parse_status || '')) ? (
            <Button size="small" loading={retryingId === record.id} onClick={() => retryParse(record)}>
              重试解析
            </Button>
          ) : null}
          <Button type="primary" ghost size="small" onClick={() => openRecord(record)}>
            {record.action || '查看'}
          </Button>
          <Popconfirm title="确认删除该历史任务？" description="会删除项目记录和已解析的结构化数据。" okText="删除" cancelText="取消" onConfirm={() => deleteRecord(record)}>
            <Button danger size="small" icon={<Trash2 size={14} />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="module-shell">
      <ModuleHeader
        title="历史记录"
        description="集中查看上传过的招标文件、解析结果、招标解读和标书编制进度，便于继续处理和追溯。"
        actions={
          <Space>
            <Input
              allowClear
              prefix={<Search size={16} />}
              placeholder="搜索项目名称、编号、招标单位"
              value={keyword}
              onChange={event => setKeyword(event.target.value)}
              className="w-80"
            />
            <Button onClick={fetchHistory}>刷新记录</Button>
          </Space>
        }
      />

      <MetricCards
        items={[
          { title: '历史项目', value: items.length, desc: '已入库招标项目', icon: FileClock, colorClass: 'bg-blue-50 text-blue-600' },
          { title: '已解读', value: items.filter(item => (item.analysis_count || 0) > 0).length, desc: '存在结构化解读', icon: ClipboardList, colorClass: 'bg-emerald-50 text-emerald-600' },
          { title: '编制中', value: items.filter(item => (item.section_count || 0) > 0).length, desc: '已生成章节大纲', icon: SquarePen, colorClass: 'bg-violet-50 text-violet-600' },
          { title: '风险项', value: items.reduce((sum, item) => sum + (item.risk_count || 0), 0), desc: '累计识别风险', icon: AlertTriangle, colorClass: 'bg-orange-50 text-orange-500' },
        ]}
      />

      <div className="grid min-h-0 grid-cols-[220px_minmax(0,1fr)] gap-4">
        <CategoryList title="记录阶段" items={stageCategories} activeName={activeStage} onChange={setActiveStage} />
        <section className="panel-card h-full overflow-hidden">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="panel-title mb-0">历史任务列表</h2>
            <Select
              value={activeStage}
              onChange={setActiveStage}
              className="w-40"
              options={stageCategories.map(item => ({ label: item.name, value: item.name }))}
            />
          </div>
          <Table
            rowKey="id"
            size="small"
            pagination={{ pageSize: 12 }}
            columns={columns}
            dataSource={filteredItems}
            loading={loading}
            className="compact-table"
            tableLayout="fixed"
            scroll={{ y: 'calc(100vh - 392px)' }}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史记录，上传招标文件后会显示在这里" /> }}
          />
        </section>
      </div>
    </div>
  );
}
