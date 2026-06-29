import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Empty, Input, Space, Tag, Typography, message } from 'antd';
import { ClipboardCheck, Database, FileWarning, ListChecks, RefreshCw, ShieldAlert, SquarePen } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { applyBidPrefillConfirmation, getBidPrefillReport, getLatestInterpretation } from '../../api/bidProject';
import type { BidPrefillField, BidPrefillReport, BidPrefillSectionCandidate, BidPrefillStatus } from '../../api/bidProject';
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

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => window.setTimeout(resolve, ms));
}

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

function emptyText(text: string): JSX.Element {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={text} />;
}

function fieldNeedsUserInput(field: BidPrefillField): boolean {
  return field.status === 'customer_required' || field.status === 'manual_confirm' || field.riskLevel === 'critical';
}

function fieldHasConfirmedValue(field: BidPrefillField, draftValues: Record<string, string>): boolean {
  return Boolean((draftValues[field.key] || '').trim());
}

function sourceDomainLabel(domain?: string): string {
  const labels: Record<string, string> = {
    tender_requirement: '招标要求',
    enterprise_fact: '泰昌企业事实',
    reference_template: '参考稿',
  };
  return labels[domain || ''] || domain || '未标注来源域';
}

export function BidPrefillPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const projectIdParam = searchParams.get('projectId');
  const fromWorkflow = searchParams.get('fromWorkflow') === '1';
  const focusFieldParam = searchParams.get('focus');
  const [projectId, setProjectId] = useState<string | null>(projectIdParam);
  const [report, setReport] = useState<BidPrefillReport | null>(null);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [autoRetrying, setAutoRetrying] = useState(false);
  const [applying, setApplying] = useState(false);
  const [activeGroup, setActiveGroup] = useState('客户确认项');
  const [onlyGaps, setOnlyGaps] = useState(false);
  const [sectionsExpanded, setSectionsExpanded] = useState(false);

  async function resolveProjectId(): Promise<string | null> {
    if (projectIdParam) return projectIdParam;
    const latest = await getLatestInterpretation();
    return latest.project?.id || null;
  }

  function buildDraft(nextReport: BidPrefillReport, resolvedProjectId: string): Record<string, string> {
    void resolvedProjectId;
    return Object.fromEntries(nextReport.fields.map(field => [
      field.key,
      formatValue(field.confirmedValue ?? field.value),
    ]));
  }

  async function loadReportWithWorkflowRetry(resolvedProjectId: string): Promise<BidPrefillReport> {
    const maxAttempts = fromWorkflow ? 4 : 1;
    let lastReport: BidPrefillReport | null = null;
    let lastError: unknown = null;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        const nextReport = await getBidPrefillReport(resolvedProjectId);
        lastReport = nextReport;
        if (!fromWorkflow || nextReport.fields.length > 0 || attempt === maxAttempts) {
          return nextReport;
        }
      } catch (error) {
        lastError = error;
        if (attempt === maxAttempts) {
          throw error;
        }
      }
      setAutoRetrying(true);
      await sleep(1200);
    }
    if (lastReport) return lastReport;
    throw lastError instanceof Error ? lastError : new Error(String(lastError || '投标确认报告加载失败'));
  }

  async function load(): Promise<void> {
    try {
      setLoading(true);
      setAutoRetrying(false);
      const resolvedProjectId = await resolveProjectId();
      setProjectId(resolvedProjectId);
      if (!resolvedProjectId) {
        setReport(null);
        setDraftValues({});
        return;
      }
      const nextReport = await loadReportWithWorkflowRetry(resolvedProjectId);
      setReport(nextReport);
      setDraftValues(buildDraft(nextReport, resolvedProjectId));
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      message.error(reason);
    } finally {
      setLoading(false);
      setAutoRetrying(false);
    }
  }

  useEffect(() => {
    void load();
  }, [projectIdParam]);

  useEffect(() => {
    if (!report || !focusFieldParam) return;
    const target = report.fields.find(field => field.key === focusFieldParam);
    if (!target) return;
    setOnlyGaps(false);
    setActiveGroup(target.group);
    window.setTimeout(() => {
      document.querySelector(`[data-prefill-field="${focusFieldParam}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 120);
  }, [focusFieldParam, report]);

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

  const exportGate = useMemo(() => {
    if (!report) {
      return {
        ready: false,
        missingRequired: [] as BidPrefillField[],
        sectionGaps: [] as Array<{ sectionTitle: string; missingLabels: string[] }>,
        unresolvedPlaceholderCount: 0,
      };
    }
    const missingRequired = report.fields.filter(field => field.requiredLevel === 'formal_required' && !fieldHasConfirmedValue(field, draftValues));
    const sectionGaps = (report.sectionCandidates || [])
      .map(candidate => {
        const missingLabels = candidate.fields
          .filter(field => field.requiredLevel === 'formal_required' && !((draftValues[field.key] || '').trim()))
          .map(field => field.label);
        return { sectionTitle: candidate.sectionTitle, missingLabels };
      })
      .filter(item => item.missingLabels.length > 0);
    const unresolvedPlaceholderCount = report.summary.unresolvedPlaceholderCount || 0;
    return {
      ready: missingRequired.length === 0 && unresolvedPlaceholderCount === 0,
      missingRequired,
      sectionGaps,
      unresolvedPlaceholderCount,
    };
  }, [draftValues, report]);

  const metrics = [
    { title: '字段总数', value: report?.summary.totalFields || 0, desc: `schema ${report?.schemaVersion || '-'}`, icon: ClipboardCheck, colorClass: 'bg-blue-50 text-blue-600' },
    { title: '系统已识别', value: report?.summary.systemRecognized || 0, desc: '来自招标解析', icon: Database, colorClass: 'bg-cyan-50 text-cyan-600' },
    { title: '企业库带出', value: report?.summary.enterpriseLibrary || 0, desc: '来自知识/资信/产品库', icon: Database, colorClass: 'bg-emerald-50 text-emerald-600' },
    { title: '客户需填写', value: report?.summary.customerRequired || 0, desc: '报价/保证金/授权等', icon: ShieldAlert, colorClass: 'bg-rose-50 text-rose-600' },
    { title: '正式必填缺口', value: report?.summary.formalRequiredGaps || 0, desc: '导出前应收口', icon: FileWarning, colorClass: 'bg-amber-50 text-amber-600' },
  ];

  const sectionCandidateCount = report?.sectionCandidates?.length || 0;
  const sectionGapCount = (report?.sectionCandidates || []).reduce((total, item) => total + (item.gapCount || 0), 0);

  function updateDraftValue(key: string, value: string): void {
    setDraftValues(prev => ({ ...prev, [key]: value }));
  }

  function resetDraftValue(field: BidPrefillField): void {
    updateDraftValue(field.key, formatValue(field.value));
  }

  function adoptSectionCandidate(candidate: BidPrefillSectionCandidate): void {
    if (!report) return;
    const fieldByKey = new Map(report.fields.map(field => [field.key, field]));
    setDraftValues(prev => {
      const next = { ...prev };
      for (const candidateField of candidate.fields) {
        const field = fieldByKey.get(candidateField.key);
        if (!field) continue;
        const value = formatValue(field.value);
        if (value.trim()) {
          next[field.key] = value;
        }
      }
      return next;
    });
  }

  function focusField(fieldKey: string): void {
    const target = report?.fields.find(field => field.key === fieldKey);
    if (!target) return;
    setOnlyGaps(false);
    setActiveGroup(target.group);
    window.setTimeout(() => {
      document.querySelector(`[data-prefill-field="${fieldKey}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 80);
  }

  async function confirmAndEnterEditor(): Promise<void> {
    if (!projectId) return;
    try {
      setApplying(true);
      const application = await applyBidPrefillConfirmation(projectId, draftValues);
      if (application.ready_for_formal_export) {
        message.success(`确认值已应用，共替换 ${application.replacement_count} 处占位符`);
      } else {
        message.warning(
          `已应用 ${application.replacement_count} 处；仍有 ${application.unresolved_placeholder_count} 处占位和 ${application.missing_formal_required_fields.length} 个正式必填缺口`,
        );
      }
      navigate(`/bid-editor?projectId=${projectId}`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setApplying(false);
    }
  }

  function renderFieldCard(field: BidPrefillField): JSX.Element {
    const confirmedValue = draftValues[field.key] ?? '';
    const candidateValue = formatValue(field.value);
    const needsInput = fieldNeedsUserInput(field);
    return (
      <article
        key={field.key}
        data-prefill-field={field.key}
        className={`prefill-field-card rounded-xl border bg-white p-5 shadow-sm ${needsInput ? 'border-rose-100' : 'border-slate-100'}`}
      >
        <div className="mb-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
          <div className="min-w-0">
            <h3 className="m-0 text-lg font-black leading-snug text-slate-950">{field.label}</h3>
            <div className="mt-2 flex flex-wrap gap-2">
              <Tag color="purple" className="m-0 max-w-full whitespace-normal">{field.group}</Tag>
              <Tag color={statusColor[field.status]} className="m-0 max-w-full whitespace-normal">{field.statusLabel}</Tag>
              <Tag color={riskColor[field.riskLevel] || 'default'} className="m-0 max-w-full whitespace-normal">{field.riskLevel}</Tag>
            </div>
          </div>
          <Button className="justify-self-start md:justify-self-end" size="small" onClick={() => resetDraftValue(field)}>恢复候选值</Button>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(280px,1fr)_minmax(320px,1fr)]">
          <div className="min-w-0 rounded-lg bg-slate-50 p-4">
            <div className="mb-1 text-xs font-bold text-slate-500">系统候选值</div>
            <Typography.Paragraph className="prefill-long-text m-0 whitespace-pre-wrap text-sm font-semibold leading-6 text-slate-700">
              {candidateValue || '暂无候选值，需人工填写'}
            </Typography.Paragraph>
          </div>
          <div className="min-w-0">
            <div className="mb-1 text-xs font-bold text-slate-500">客户确认值</div>
            <Input.TextArea
              value={confirmedValue}
              autoSize={{ minRows: 2, maxRows: 6 }}
              className="prefill-confirm-textarea"
              placeholder={needsInput ? '请填写或确认该字段' : '可按实际情况修正'}
              onChange={event => updateDraftValue(field.key, event.target.value)}
            />
          </div>
        </div>

        <div className="mt-4 grid gap-2 text-xs font-semibold leading-5 text-slate-500 xl:grid-cols-3">
          <div className="prefill-long-text min-w-0">来源规则：{field.sourcePolicy || '-'}</div>
          <div className="prefill-long-text min-w-0">依据：{field.evidence?.sourceLabel || '-'}</div>
          <div className="prefill-long-text min-w-0">映射：{field.mapsTo?.join('、') || '-'}</div>
        </div>
      </article>
    );
  }

  function renderSectionCandidate(candidate: BidPrefillSectionCandidate): JSX.Element {
    return (
      <article key={`${candidate.sectionId || candidate.sectionTitle}`} className="prefill-section-candidate rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="m-0 min-w-0 text-base font-black text-slate-950">{candidate.sectionTitle}</h3>
              {candidate.virtual ? <Tag className="m-0">虚拟章节</Tag> : null}
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              <Tag color={candidate.gapCount ? 'orange' : 'green'} className="m-0">缺口 {candidate.gapCount}</Tag>
              <Tag className="m-0">候选 {candidate.fieldCount}</Tag>
              {(candidate.sourceDomains || []).map(domain => (
                <Tag key={domain} color={domain === 'enterprise_fact' ? 'green' : 'blue'} className="m-0">
                  {sourceDomainLabel(domain)}
                </Tag>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-start justify-start gap-2 lg:justify-end">
            <Button size="small" onClick={() => adoptSectionCandidate(candidate)}>采纳本章候选</Button>
            {Object.entries(candidate.statusCounts || {}).map(([status, count]) => (
              <Tag key={status} color={statusColor[status as BidPrefillStatus] || 'default'} className="m-0">
                {status === 'manual_confirm' ? '待确认' : status === 'customer_required' ? '需填写' : status} {count}
              </Tag>
            ))}
          </div>
        </div>

        {candidate.boundaryWarnings?.length ? (
          <div className="mt-3 grid gap-1">
            {candidate.boundaryWarnings.map(warning => (
              <div key={warning} className="prefill-section-warning">{warning}</div>
            ))}
          </div>
        ) : null}

        <div className="mt-3 grid gap-2">
          {candidate.fields.map(field => (
            <button
              key={field.key}
              type="button"
              className="prefill-section-field"
              onClick={() => focusField(field.key)}
            >
              <span className="min-w-0">
                <strong>{field.label}</strong>
                <span>{field.valuePreview || '暂无候选值'}</span>
              </span>
              <Tag color={statusColor[field.status]} className="m-0 shrink-0">{field.statusLabel}</Tag>
            </button>
          ))}
        </div>
      </article>
    );
  }

  return (
    <div className="prefill-shell relative">
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
              loading={applying}
              onClick={() => void confirmAndEnterEditor()}
            >
              确认、应用并进入正文编辑
            </Button>
          </>
        }
      />

      <Alert
        className="prefill-alert"
        type={fromWorkflow ? 'warning' : 'info'}
        showIcon
        message={fromWorkflow ? '请先确认关键投标字段，再应用到正文占位符' : '优先确认客户需填写和待人工确认字段'}
        description={autoRetrying
          ? '正在等待分册大纲和投标确认字段同步完成，请稍候。'
          : '报价、保证金、授权签章、税率等字段确认后再进入正文编辑；章节候选和缺口清单已收起，可作为辅助核对。'}
      />

      {report ? (
        <>
          <div className="prefill-workspace">
            <section className="panel-card prefill-sidebar">
              <h2 className="panel-title">字段分组</h2>
              <div className="prefill-group-list">
                {groups.map(group => (
                  <button
                    key={group.name}
                    type="button"
                    className={`flex min-h-11 w-full min-w-0 items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm font-bold ${
                      activeGroup === group.name ? 'bg-blue-50 text-blue-600' : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
                    }`}
                    onClick={() => setActiveGroup(group.name)}
                  >
                    <span className="prefill-group-name">{group.name}</span>
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

            <section className="prefill-main">
              <div className="mb-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
                <div className="min-w-0">
                  <h2 className="panel-title mb-1">变量确认</h2>
                  <p className="m-0 text-sm font-semibold leading-6 text-slate-500">
                    先确认会影响投标文件生成和正式导出的字段；系统候选值仅作参考，客户确认值会用于后续正文占位替换。
                  </p>
                </div>
                <Space className="justify-start md:justify-end" wrap>
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

          <section className="panel-card prefill-export-gate">
            <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div className="min-w-0">
                <h2 className="panel-title mb-1">导出前门禁</h2>
                <p className="m-0 text-sm font-semibold leading-6 text-slate-500">
                  只检查客户确认值和明确占位符，不生成正文；未通过时仍可保存确认值，但不应作为正式标书导出。
                </p>
              </div>
              <Space className="justify-start lg:justify-end" wrap>
                <Tag color={exportGate.ready ? 'green' : 'red'}>{exportGate.ready ? '可进入正式导出' : '仍需收口'}</Tag>
                <Tag color={exportGate.missingRequired.length ? 'red' : 'green'}>必填缺口 {exportGate.missingRequired.length}</Tag>
                <Tag color={exportGate.unresolvedPlaceholderCount ? 'orange' : 'green'}>正文占位 {exportGate.unresolvedPlaceholderCount}</Tag>
              </Space>
            </div>
            {exportGate.missingRequired.length || exportGate.sectionGaps.length ? (
              <div className="prefill-gate-list mt-3">
                {exportGate.missingRequired.slice(0, 8).map(field => (
                  <button key={field.key} type="button" className="prefill-gate-item" onClick={() => focusField(field.key)}>
                    <strong>{field.label}</strong>
                    <span>{field.group} · {field.statusLabel}</span>
                  </button>
                ))}
                {exportGate.missingRequired.length > 8 ? (
                  <div className="prefill-section-warning">还有 {exportGate.missingRequired.length - 8} 个必填缺口未展示，请切换“只看需确认”。</div>
                ) : null}
              </div>
            ) : (
              <div className="prefill-gate-pass mt-3">当前确认值已覆盖正式必填字段；仍需以应用后的占位符扫描结果为最终门禁。</div>
            )}
          </section>

          <MetricCards items={metrics} />

          <section className="panel-card">
            <div className="grid gap-3 text-sm font-semibold text-slate-600 lg:grid-cols-[minmax(0,2fr)_minmax(150px,0.7fr)_minmax(190px,0.9fr)_minmax(150px,0.7fr)]">
              <div className="prefill-meta-item">
                <span className="prefill-meta-label">项目</span>
                <strong>{report.project?.project_name || '未命名项目'}</strong>
              </div>
              <div className="prefill-meta-item">
                <span className="prefill-meta-label">招标编号</span>
                <strong>{report.project?.project_no || '-'}</strong>
              </div>
              <div className="prefill-meta-item">
                <span className="prefill-meta-label">生成时间</span>
                <strong>{report.generatedAt}</strong>
              </div>
              <div className="prefill-meta-item">
                <span className="prefill-meta-label">确认方式</span>
                <strong>客户人工确认</strong>
              </div>
            </div>
          </section>

          <section className="panel-card prefill-section-review">
            <div className="mb-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
              <div className="min-w-0">
                <h2 className="panel-title mb-1 flex items-center gap-2">
                  <ListChecks size={18} />
                  章节候选与缺口清单
                </h2>
                <p className="m-0 text-sm font-semibold leading-6 text-slate-500">
                  将结构化货物清单、技术参数表、偏差表和泰昌参数佐证按章节归类展示；这里只做确认提示，不自动生成正文。
                </p>
              </div>
              <Space className="justify-start md:justify-end" wrap>
                <Tag color="blue">章节 {sectionCandidateCount}</Tag>
                <Tag color="orange">缺口 {sectionGapCount}</Tag>
                <Button size="small" onClick={() => setSectionsExpanded(value => !value)}>
                  {sectionsExpanded ? '收起辅助清单' : '展开辅助清单'}
                </Button>
              </Space>
            </div>
            {!sectionsExpanded ? (
              <div className="prefill-section-collapsed">
                章节候选和缺口清单已作为辅助核对项收起。需要追溯字段归属、采纳章节候选或查看边界告警时，可展开查看。
              </div>
            ) : report.sectionCandidates?.length ? (
              <div className="prefill-section-grid">
                {report.sectionCandidates.map(renderSectionCandidate)}
              </div>
            ) : emptyText('暂无章节级候选，请先生成分册大纲或补充结构化资料')}
          </section>

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
