import { Alert, Button, Modal, Select, Space, Table, Tag, Tooltip, message } from 'antd';
import { Bot, Calculator, CircleDollarSign, RefreshCcw, ShieldCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { apiClient } from '../../api/client';
import { MetricCards } from '../../components/common/MetricCards';
import { ModuleHeader } from '../../components/common/ModuleHeader';

interface UsageSummary {
  call_count?: number;
  success_count?: number;
  failed_count?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  input_cost?: number;
  output_cost?: number;
  other_cost?: number;
  total_cost?: number;
  currency?: string;
  first_call_at?: string | null;
  last_call_at?: string | null;
}

interface UsageProject {
  id: string;
  project_name?: string | null;
  status?: string | null;
  created_at?: string | null;
  call_count?: number;
  total_tokens?: number;
  total_cost?: number;
  last_call_at?: string | null;
}

interface UsageStage {
  project_id?: string;
  stage: string;
  provider: string;
  model: string;
  operation_type: string;
  call_count: number;
  success_count: number;
  failed_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_cost: number;
}

interface UsageLog {
  id: string;
  project_id?: string;
  file_id?: string;
  section_id?: string;
  provider: string;
  model: string;
  operation_type: string;
  stage: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  input_cost?: number;
  output_cost?: number;
  other_cost?: number;
  total_cost: number;
  currency: string;
  success: boolean;
  usage_estimated: boolean;
  cost_estimated: boolean;
  is_stream?: boolean;
  latency_ms?: number;
  status_code?: number;
  created_at: string;
}

interface UsageOverview {
  summary?: UsageSummary;
  project?: UsageProject;
  projects?: UsageProject[];
  stages?: UsageStage[];
  operationSummary?: UsageStage[];
  recentLogs?: UsageLog[];
}

const operationLabels: Record<string, { label: string; color: string }> = {
  text_generation: { label: '文本模型', color: 'blue' },
  chat_completion: { label: '文本模型', color: 'blue' },
  embedding: { label: '向量模型', color: 'green' },
  rerank: { label: '重排模型', color: 'purple' },
  ocr: { label: 'OCR 解析', color: 'orange' },
  vision: { label: '视觉模型', color: 'cyan' },
  other: { label: '其他调用', color: 'default' },
};

const stageLabels: Record<string, string> = {
  ai_interpretation_report: '招标文件解读',
  bid_outline_generation: '分册大纲生成',
  bid_section_stream: '章节正文生成',
  bid_section_sync_fallback: '章节正文补偿生成',
  compliance_supplement: '条款补强',
  knowledge_embedding: '知识库向量化',
  knowledge_rerank: '知识库重排',
};

function formatNumber(value?: number): string {
  return Number(value || 0).toLocaleString('zh-CN');
}

function formatCost(value?: number): string {
  return `¥${Number(value || 0).toFixed(4)}`;
}

function formatDateTime(value?: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN') : '-';
}

function getOperationMeta(operationType?: string) {
  return operationLabels[operationType || 'other'] || operationLabels.other;
}

function getStageLabel(stage?: string): string {
  return stageLabels[stage || ''] || stage || '-';
}

export function UsageCostPage(): JSX.Element {
  const [overview, setOverview] = useState<UsageOverview>({});
  const [loading, setLoading] = useState(false);
  const [selectedProjectId, setSelectedProjectId] = useState<string>();
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailOverview, setDetailOverview] = useState<UsageOverview>({});

  const fetchUsageOverview = async (projectId?: string | null) => {
    try {
      setLoading(true);
      const effectiveProjectId = projectId === undefined ? selectedProjectId : projectId || undefined;
      const query = effectiveProjectId ? `?days=30&projectId=${effectiveProjectId}` : '?days=30';
      const { data } = await apiClient.get<UsageOverview>(`/api/bidding/ai-usage${query}`, { skipGlobalLoading: true });
      setOverview(data || {});
    } catch (error: any) {
      message.error(error.message || '读取用量与成本统计失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsageOverview(null);
  }, []);

  const openProjectDetail = async (project: UsageProject) => {
    try {
      setDetailOpen(true);
      setDetailLoading(true);
      const { data } = await apiClient.get<UsageOverview>(`/api/bidding/ai-usage?days=30&projectId=${project.id}`, { skipGlobalLoading: true });
      setDetailOverview(data || {});
    } catch (error: any) {
      message.error(error.message || '读取项目用量明细失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const selectedProject = useMemo(
    () => overview.projects?.find(project => project.id === selectedProjectId),
    [overview.projects, selectedProjectId],
  );
  const summary = overview.summary || {};
  const successRate = summary.call_count
    ? `${Math.round(((summary.success_count || 0) / summary.call_count) * 100)}%`
    : '-';

  return (
    <div className="usage-cost-shell">
      <ModuleHeader
        title="用量与成本"
        description="按项目追踪标书生成、向量检索和重排调用的 Token、模型、成功率与人民币预估成本。"
        actions={
          <Space>
            <Select
              allowClear
              showSearch
              className="min-w-[360px]"
              placeholder="全部标书项目"
              value={selectedProjectId}
              optionFilterProp="label"
              onChange={value => {
                setSelectedProjectId(value);
                fetchUsageOverview(value || null);
              }}
              options={(overview.projects || []).map(project => ({
                value: project.id,
                label: `${project.project_name || project.id} · ${formatCost(project.total_cost)} · ${formatNumber(project.total_tokens)} Token`,
              }))}
            />
            <Button icon={<RefreshCcw size={16} />} loading={loading} onClick={() => fetchUsageOverview()}>
              刷新
            </Button>
          </Space>
        }
      />

      <MetricCards
        items={[
          { title: selectedProjectId ? '单项目预估成本' : '近 30 天预估成本', value: formatCost(summary.total_cost), desc: '人民币 CNY', icon: CircleDollarSign, colorClass: 'bg-amber-50 text-amber-600' },
          { title: '总 Token', value: formatNumber(summary.total_tokens), desc: `输入 ${formatNumber(summary.input_tokens)} / 输出 ${formatNumber(summary.output_tokens)}`, icon: Calculator, colorClass: 'bg-blue-50 text-blue-600' },
          { title: '调用次数', value: formatNumber(summary.call_count), desc: `成功 ${formatNumber(summary.success_count)} / 失败 ${formatNumber(summary.failed_count)}`, icon: Bot, colorClass: 'bg-emerald-50 text-emerald-600' },
          { title: '调用成功率', value: successRate, desc: selectedProject?.project_name || '全部项目', icon: ShieldCheck, colorClass: 'bg-violet-50 text-violet-600' },
        ]}
      />

      <Alert
        showIcon
        className="rounded-2xl"
        type="info"
        message="成本统计口径"
        description="系统按 ai_model_prices 中的人民币单价和每次调用返回的 usage 计算成本；若历史价格仍为 USD，后端会按 AI_USAGE_USD_TO_CNY_RATE 折算为 CNY 返回。流式调用或部分厂商未返回 usage 时，会按文本长度估算并在明细中标记。最终费用仍应以模型厂商账单为准。"
      />

      <section className="panel-card usage-cost-panel">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-black text-slate-900">模型类型成本拆分</h2>
            <p className="text-sm font-semibold text-slate-500">区分文本模型、向量模型、重排模型和 OCR，便于判断成本来源。</p>
          </div>
        </div>
        <Table<UsageStage>
          rowKey={record => `${record.provider}-${record.model}-${record.operation_type}-${record.stage || 'global'}`}
          className="compact-table"
          size="small"
          loading={loading}
          dataSource={selectedProjectId ? overview.stages || [] : overview.operationSummary || []}
          pagination={(selectedProjectId ? overview.stages || [] : overview.operationSummary || []).length > 6 ? { pageSize: 6, showSizeChanger: false } : false}
          scroll={{ x: 980, y: 260 }}
          sticky
          tableLayout="fixed"
          columns={[
            {
              title: selectedProjectId ? '业务阶段' : '模型类型',
              dataIndex: 'stage',
              width: 180,
              render: (_, record) => selectedProjectId ? getStageLabel(record.stage) : (
                <Tag color={getOperationMeta(record.operation_type).color}>{getOperationMeta(record.operation_type).label}</Tag>
              ),
            },
            {
              title: '模型',
              width: 240,
              render: (_, record) => (
                <div className="flex flex-col">
                  <span className="font-bold text-slate-900">{record.model || '-'}</span>
                  <span className="text-xs font-semibold text-slate-500">{record.provider} · {record.operation_type}</span>
                </div>
              ),
            },
            { title: '调用', dataIndex: 'call_count', width: 100, render: value => formatNumber(value) },
            { title: '成功', dataIndex: 'success_count', width: 100, render: value => formatNumber(value) },
            { title: '失败', dataIndex: 'failed_count', width: 100, render: value => formatNumber(value) },
            {
              title: 'Token',
              width: 220,
              render: (_, record) => (
                <span>{formatNumber(record.total_tokens)} <span className="text-slate-400">({formatNumber(record.input_tokens)} / {formatNumber(record.output_tokens)})</span></span>
              ),
            },
            { title: '人民币成本', dataIndex: 'total_cost', width: 140, render: value => formatCost(value) },
          ]}
        />
      </section>

      <section className="panel-card usage-cost-panel">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-black text-slate-900">标书项目成本汇总</h2>
            <p className="text-sm font-semibold text-slate-500">按标书项目展示总 Token、调用次数、人民币成本和最近调用时间；点击查看进入完整调用明细。</p>
          </div>
        </div>
        <Table<UsageProject>
          rowKey="id"
          className="compact-table"
          size="small"
          loading={loading}
          dataSource={overview.projects || []}
          pagination={{ pageSize: 10, showSizeChanger: true, pageSizeOptions: [10, 20, 50], showTotal: total => `共 ${total} 个项目` }}
          scroll={{ x: 1120, y: 520 }}
          sticky
          tableLayout="fixed"
          columns={[
            {
              title: '标书项目',
              dataIndex: 'project_name',
              width: 420,
              render: (_, record) => (
                <div className="min-w-0">
                  <div className="truncate font-bold text-slate-900">{record.project_name || record.id}</div>
                  <div className="mt-1 text-xs font-semibold text-slate-500">ID：{record.id}</div>
                </div>
              ),
            },
            { title: '创建时间', dataIndex: 'created_at', width: 170, render: value => formatDateTime(value) },
            { title: '最近调用', dataIndex: 'last_call_at', width: 170, render: value => formatDateTime(value) },
            { title: '调用次数', dataIndex: 'call_count', width: 110, render: value => formatNumber(value) },
            {
              title: 'Token',
              dataIndex: 'total_tokens',
              width: 150,
              render: value => <span className="font-bold text-slate-900">{formatNumber(value)}</span>,
            },
            {
              title: '人民币成本',
              dataIndex: 'total_cost',
              width: 140,
              render: value => <span className="font-bold text-slate-900">{formatCost(value)}</span>,
            },
            {
              title: '状态',
              dataIndex: 'status',
              width: 120,
              render: value => <Tag color={value === 'uploaded' ? 'blue' : 'default'}>{value || '-'}</Tag>,
            },
            {
              title: '操作',
              width: 110,
              render: (_, record) => (
                <Button type="link" className="px-0 font-bold" onClick={() => openProjectDetail(record)}>
                  查看
                </Button>
              ),
            },
          ]}
        />
      </section>

      <Modal
        open={detailOpen}
        title="标书项目调用明细"
        width={1280}
        footer={null}
        destroyOnClose
        onCancel={() => {
          setDetailOpen(false);
          setDetailOverview({});
        }}
      >
        <div className="space-y-4">
          <MetricCards
            items={[
              { title: '项目成本', value: formatCost(detailOverview.summary?.total_cost), desc: '人民币 CNY', icon: CircleDollarSign, colorClass: 'bg-amber-50 text-amber-600' },
              { title: '总 Token', value: formatNumber(detailOverview.summary?.total_tokens), desc: `输入 ${formatNumber(detailOverview.summary?.input_tokens)} / 输出 ${formatNumber(detailOverview.summary?.output_tokens)}`, icon: Calculator, colorClass: 'bg-blue-50 text-blue-600' },
              { title: '调用次数', value: formatNumber(detailOverview.summary?.call_count), desc: `成功 ${formatNumber(detailOverview.summary?.success_count)} / 失败 ${formatNumber(detailOverview.summary?.failed_count)}`, icon: Bot, colorClass: 'bg-emerald-50 text-emerald-600' },
              { title: '最近调用', value: detailOverview.summary?.last_call_at ? new Date(detailOverview.summary.last_call_at).toLocaleTimeString('zh-CN') : '-', desc: detailOverview.project?.project_name || '当前标书项目', icon: ShieldCheck, colorClass: 'bg-violet-50 text-violet-600' },
            ]}
          />
          <section className="usage-cost-panel">
            <h3 className="mb-3 text-base font-black text-slate-900">阶段成本拆分</h3>
            <Table<UsageStage>
              rowKey={record => `${record.stage}-${record.provider}-${record.model}-${record.operation_type}`}
              className="compact-table"
              size="small"
              loading={detailLoading}
              dataSource={detailOverview.stages || []}
              pagination={false}
              scroll={{ x: 980, y: 220 }}
              tableLayout="fixed"
              columns={[
                { title: '业务阶段', dataIndex: 'stage', width: 180, render: value => getStageLabel(value) },
                {
                  title: '模型',
                  width: 240,
                  render: (_, record) => (
                    <div className="flex flex-col">
                      <span className="font-bold text-slate-900">{record.model || '-'}</span>
                      <span className="text-xs font-semibold text-slate-500">{record.provider} · {record.operation_type}</span>
                    </div>
                  ),
                },
                { title: '调用', dataIndex: 'call_count', width: 90, render: value => formatNumber(value) },
                { title: '成功', dataIndex: 'success_count', width: 90, render: value => formatNumber(value) },
                { title: '失败', dataIndex: 'failed_count', width: 90, render: value => formatNumber(value) },
                { title: 'Token', dataIndex: 'total_tokens', width: 150, render: value => formatNumber(value) },
                { title: '人民币成本', dataIndex: 'total_cost', width: 130, render: value => formatCost(value) },
              ]}
            />
          </section>
          <section className="usage-cost-panel">
            <h3 className="mb-3 text-base font-black text-slate-900">完整调用明细</h3>
            <Table<UsageLog>
              rowKey="id"
              className="compact-table"
              size="small"
              loading={detailLoading}
              dataSource={detailOverview.recentLogs || []}
              pagination={{ pageSize: 10, showSizeChanger: true, pageSizeOptions: [10, 20, 50], showTotal: total => `共 ${total} 条调用` }}
              scroll={{ x: 1380, y: 420 }}
              tableLayout="fixed"
              columns={[
                { title: '时间', dataIndex: 'created_at', width: 170, render: value => formatDateTime(value) },
                {
                  title: '调用类型',
                  dataIndex: 'operation_type',
                  width: 120,
                  render: value => {
                    const meta = getOperationMeta(value);
                    return <Tag color={meta.color}>{meta.label}</Tag>;
                  },
                },
                { title: '业务阶段', dataIndex: 'stage', width: 170, render: value => getStageLabel(value) },
                {
                  title: '模型 / 协议',
                  width: 230,
                  render: (_, record) => (
                    <div className="flex flex-col">
                      <span className="font-bold text-slate-900">{record.model || '-'}</span>
                      <span className="text-xs font-semibold text-slate-500">{record.provider} · {record.is_stream ? 'stream' : 'sync'}</span>
                    </div>
                  ),
                },
                {
                  title: 'Token',
                  width: 220,
                  render: (_, record) => (
                    <Tooltip title={`输入 ${formatNumber(record.input_tokens)}，输出 ${formatNumber(record.output_tokens)}`}>
                      <span className="font-semibold">{formatNumber(record.total_tokens)} <span className="text-slate-400">({formatNumber(record.input_tokens)} / {formatNumber(record.output_tokens)})</span></span>
                    </Tooltip>
                  ),
                },
                { title: '输入费用', dataIndex: 'input_cost', width: 110, render: value => formatCost(value) },
                { title: '输出费用', dataIndex: 'output_cost', width: 110, render: value => formatCost(value) },
                { title: '合计费用', dataIndex: 'total_cost', width: 120, render: value => formatCost(value) },
                { title: '耗时', dataIndex: 'latency_ms', width: 100, render: value => value ? `${value} ms` : '-' },
                {
                  title: '状态',
                  width: 160,
                  render: (_, record) => (
                    <div className="flex flex-wrap gap-1">
                      <Tag color={record.success ? 'green' : 'red'}>{record.success ? '成功' : '失败'}</Tag>
                      {record.usage_estimated ? <Tag color="orange">Token估算</Tag> : null}
                      {record.cost_estimated ? <Tag color="blue">费用预估</Tag> : null}
                    </div>
                  ),
                },
                {
                  title: '章节',
                  width: 120,
                  render: (_, record) => record.section_id ? record.section_id.slice(0, 8) : '-',
                },
              ]}
            />
          </section>
        </div>
      </Modal>
    </div>
  );
}
