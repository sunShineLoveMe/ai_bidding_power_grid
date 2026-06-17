import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Empty, Input, Space, Tag, Typography, message } from 'antd';
import { ClipboardCheck, Database, FileWarning, RefreshCw, ShieldAlert, SquarePen } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getBidPrefillReport, getLatestInterpretation } from '../../api/bidProject';
import type { BidPrefillField, BidPrefillReport, BidPrefillStatus } from '../../api/bidProject';
import { MetricCards } from '../../components/common/MetricCards';
import { ModuleHeader } from '../../components/common/ModuleHeader';

const statusColor: Record<BidPrefillStatus, string> = {
  system_recognized: 'blue',
  enterprise_library: 'green',
  customer_required: 'red',
  manual_confirm: 'orange',
};

const riskColor: Record<string, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'blue',
  low: 'default',
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '';
  if (Array.isArray(value)) {
    return value.map(item => {
      if (item && typeof item === 'object' && 'title' in item) {
        return String((item as { title?: string }).title || '');
      }
      return String(item);
    }).filter(Boolean).join('；');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

function confirmedStorageKey(projectId: string): string {
  return `bidPrefillConfirmed:${projectId}`;
}

function emptyText(text: string): JSX.Element {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={text} />;
}

function fieldNeedsUserInput(field: BidPrefillField): boolean {
  return field.status === 'customer_required' || field.status === 'manual_confirm' || field.riskLevel === 'critical';
}

export function BidPrefillPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const projectIdParam = searchParams.get('projectId');
  const fromWorkflow = searchParams.get('fromWorkflow') === '1';
  const [projectId, setProjectId] = useState<string | null>(projectIdParam);
  const [report, setReport] = useState<BidPrefillReport | null>(null);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [activeGroup, setActiveGroup] = useState('全部字段');
  const [onlyGaps, setOnlyGaps] = useState(false);

  async function resolveProjectId(): Promise<string | null> {
    if (projectIdParam) return projectIdParam;
    const latest = await getLatestInterpretation();
    return latest.project?.id || null;
  }

  function buildDraft(nextReport: BidPrefillReport, resolvedProjectId: string): Record<string, string> {
    const base = Object.fromEntries(nextReport.fields.map(field => [field.key, formatValue(field.value)]));
    try {
      const saved = JSON.parse(localStorage.getItem(confirmedStorageKey(resolvedProjectId)) || '{}') as Record<string, string>;
      return { ...base, ...saved };
    } catch {
      return base;
    }
  }

  async function load(): Promise<void> {
    try {
      setLoading(true);
      const resolvedProjectId = await resolveProjectId();
      setProjectId(resolvedProjectId);
      if (!resolvedProjectId) {
        setReport(null);
        setDraftValues({});
        return;
      }
      const nextReport = await getBidPrefillReport(resolvedProjectId);
      setReport(nextReport);
      setDraftValues(buildDraft(nextReport, resolvedProjectId));
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      message.error(reason);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [projectIdParam]);

  const groups = useMemo(() => {
    const reportGroups = report?.groups || [];
    return [
      { name: '全部字段', count: report?.fields.length || 0 },
      { name: '客户确认项', count: report?.fields.filter(fieldNeedsUserInput).length || 0 },
      ...reportGroups.map(group => ({ name: group.name, count: group.fields.length })),
    ];
  }, [report]);

  const fields = useMemo(() => {
    if (!report) return [];
    let candidates = report.fields;
    if (activeGroup === '客户确认项') {
      candidates = candidates.filter(fieldNeedsUserInput);
    } else if (activeGroup !== '全部字段') {
      candidates = candidates.filter(field => field.group === activeGroup);
    }
    if (onlyGaps) {
      candidates = candidates.filter(fieldNeedsUserInput);
    }
    return candidates;
  }, [activeGroup, onlyGaps, report]);

  const metrics = [
    { title: '字段总数', value: report?.summary.totalFields || 0, desc: `schema ${report?.schemaVersion || '-'}`, icon: ClipboardCheck, colorClass: 'bg-blue-50 text-blue-600' },
    { title: '系统已识别', value: report?.summary.systemRecognized || 0, desc: '来自招标解析', icon: Database, colorClass: 'bg-cyan-50 text-cyan-600' },
    { title: '企业库带出', value: report?.summary.enterpriseLibrary || 0, desc: '来自知识/资信/产品库', icon: Database, colorClass: 'bg-emerald-50 text-emerald-600' },
    { title: '客户需填写', value: report?.summary.customerRequired || 0, desc: '报价/保证金/授权等', icon: ShieldAlert, colorClass: 'bg-rose-50 text-rose-600' },
    { title: '正式必填缺口', value: report?.summary.formalRequiredGaps || 0, desc: '导出前应收口', icon: FileWarning, colorClass: 'bg-amber-50 text-amber-600' },
  ];

  function updateDraftValue(key: string, value: string): void {
    setDraftValues(prev => ({ ...prev, [key]: value }));
  }

  function resetDraftValue(field: BidPrefillField): void {
    updateDraftValue(field.key, formatValue(field.value));
  }

  function confirmAndEnterEditor(): void {
    if (!projectId) return;
    localStorage.setItem(confirmedStorageKey(projectId), JSON.stringify(draftValues));
    message.success('投标关键信息已确认');
    navigate(`/bid-editor?projectId=${projectId}`);
  }

  function renderFieldCard(field: BidPrefillField): JSX.Element {
    const confirmedValue = draftValues[field.key] ?? '';
    const candidateValue = formatValue(field.value);
    const needsInput = fieldNeedsUserInput(field);
    return (
      <article
        key={field.key}
        className={`rounded-lg border bg-white p-4 shadow-sm ${needsInput ? 'border-rose-100' : 'border-slate-100'}`}
      >
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="m-0 break-words text-base font-black text-slate-950">{field.label}</h3>
            <div className="mt-2 flex flex-wrap gap-2">
              <Tag color="purple" className="m-0 max-w-full whitespace-normal break-words">{field.group}</Tag>
              <Tag color={statusColor[field.status]} className="m-0">{field.statusLabel}</Tag>
              <Tag color={riskColor[field.riskLevel] || 'default'} className="m-0">{field.riskLevel}</Tag>
            </div>
          </div>
          <Button size="small" onClick={() => resetDraftValue(field)}>恢复候选值</Button>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="min-w-0 rounded-md bg-slate-50 p-3">
            <div className="mb-1 text-xs font-bold text-slate-500">系统候选值</div>
            <Typography.Paragraph className="m-0 whitespace-pre-wrap break-words text-sm font-semibold text-slate-700">
              {candidateValue || '暂无候选值，需人工填写'}
            </Typography.Paragraph>
          </div>
          <div className="min-w-0">
            <div className="mb-1 text-xs font-bold text-slate-500">客户确认值</div>
            <Input.TextArea
              value={confirmedValue}
              autoSize={{ minRows: 2, maxRows: 6 }}
              placeholder={needsInput ? '请填写或确认该字段' : '可按实际情况修正'}
              onChange={event => updateDraftValue(field.key, event.target.value)}
            />
          </div>
        </div>

        <div className="mt-3 grid gap-2 text-xs font-semibold leading-5 text-slate-500 lg:grid-cols-3">
          <div className="min-w-0 break-words">来源规则：{field.sourcePolicy || '-'}</div>
          <div className="min-w-0 break-words">依据：{field.evidence?.sourceLabel || '-'}</div>
          <div className="min-w-0 break-words">映射：{field.mapsTo?.join('、') || '-'}</div>
        </div>
      </article>
    );
  }

  return (
    <div className="module-shell relative">
      <ModuleHeader
        title="投标信息确认"
        description="生成正文前确认项目变量、企业资料候选和客户决策字段；确认结果用于进入正文编辑前的人工收口。"
        actions={
          <>
            <Button icon={<RefreshCw size={16} />} loading={loading} onClick={load}>刷新报告</Button>
            <Button
              type="primary"
              icon={<SquarePen size={16} />}
              disabled={!projectId}
              onClick={confirmAndEnterEditor}
            >
              确认并进入正文编辑
            </Button>
          </>
        }
      />

      <Alert
        className="my-4"
        type={fromWorkflow ? 'warning' : 'info'}
        showIcon
        message={fromWorkflow ? '请先确认关键投标字段，再进入正文编辑' : '投标确认不会自动覆盖已生成正文'}
        description="报价、保证金、授权签章、税率等客户决策字段必须人工填写或确认；当前确认值先作为本地确认草稿保存，不直接改写 bid_sections 或 sectionsSnapshot。"
      />

      {report ? (
        <>
          <MetricCards items={metrics} />

          <section className="panel-card my-4">
            <div className="grid gap-3 text-sm font-semibold text-slate-600 lg:grid-cols-4">
              <div className="min-w-0 break-words"><span className="text-slate-400">项目：</span>{report.project?.project_name || '未命名项目'}</div>
              <div className="min-w-0 break-words"><span className="text-slate-400">招标编号：</span>{report.project?.project_no || '-'}</div>
              <div className="min-w-0 break-words"><span className="text-slate-400">生成时间：</span>{report.generatedAt}</div>
              <div className="min-w-0 break-words"><span className="text-slate-400">确认方式：</span>客户人工确认</div>
            </div>
          </section>

          <div className="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)]">
            <section className="panel-card self-start">
              <h2 className="panel-title">字段分组</h2>
              <div className="grid gap-2">
                {groups.map(group => (
                  <button
                    key={group.name}
                    type="button"
                    className={`flex min-h-11 items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm font-bold ${
                      activeGroup === group.name ? 'bg-blue-50 text-blue-600' : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
                    }`}
                    onClick={() => setActiveGroup(group.name)}
                  >
                    <span className="min-w-0 break-words">{group.name}</span>
                    <Tag className="m-0 shrink-0">{group.count}</Tag>
                  </button>
                ))}
              </div>
              <Button
                className="mt-4 w-full"
                type={onlyGaps ? 'primary' : 'default'}
                onClick={() => setOnlyGaps(value => !value)}
              >
                {onlyGaps ? '显示全部字段' : '只看需确认'}
              </Button>
            </section>

            <section className="min-w-0">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h2 className="panel-title mb-0">变量确认</h2>
                <Space wrap>
                  <Tag color="red">客户需填写 {report.gapReport.customerRequiredFields.length}</Tag>
                  <Tag color="orange">待人工确认 {report.gapReport.manualConfirmFields.length}</Tag>
                  <Tag>当前 {fields.length} 个字段</Tag>
                </Space>
              </div>
              <div className="grid gap-3">
                {fields.length ? fields.map(renderFieldCard) : (
                  <section className="panel-card">{emptyText('当前分组暂无字段')}</section>
                )}
              </div>
            </section>
          </div>

          <section className="panel-card mt-4">
            <h2 className="panel-title">预填来源规则</h2>
            <ul className="m-0 grid gap-2 pl-5 text-sm font-semibold leading-6 text-slate-600">
              {report.sourceRules.map(rule => <li key={rule} className="break-words">{rule}</li>)}
            </ul>
          </section>
        </>
      ) : (
        <section className="panel-card">
          {emptyText(projectId ? '当前项目暂无投标确认报告' : '暂无可用项目，请先上传并解析招标文件')}
        </section>
      )}
    </div>
  );
}
