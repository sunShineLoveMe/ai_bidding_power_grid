import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Empty, Select, Skeleton, Space, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { AlertTriangle, ArrowRight, CheckCircle2, ClipboardCheck, FileWarning, RefreshCw, ShieldCheck } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getFormalCheckReport, getLatestInterpretation } from '../../api/bidProject';
import type { FormalCheckItem, FormalCheckReport, FormalCheckStatus } from '../../api/bidProject';
import { MetricCards } from '../../components/common/MetricCards';
import { ModuleHeader } from '../../components/common/ModuleHeader';
import { formatDateTime } from '../../utils/time';

const statusColor: Record<FormalCheckStatus, string> = {
  passed: 'green',
  blocked: 'red',
  warning: 'orange',
  manual_confirm: 'blue',
  not_applicable: 'default',
};

const severityColor: Record<FormalCheckItem['severity'], string> = {
  blocker: 'red',
  high: 'orange',
  medium: 'blue',
  low: 'default',
};

const severityLabel: Record<FormalCheckItem['severity'], string> = {
  blocker: '阻断',
  high: '高',
  medium: '中',
  low: '低',
};

const internalTokenLabels: Record<string, string> = {
  'formal_bid_check_rules.v1': '国家电网投标文件正式检查规则第一版',
  formal_bid_check_rules: '正式检查规则',
  total_bid_price_upper: '投标总价大写',
  total_bid_price: '投标总价',
  price_tax_policy: '价格税费口径',
  bid_bond_amount: '投标保证金金额',
  bid_bond_form: '投标保证金形式',
  authorized_representative_phone: '授权代表联系方式',
  authorized_representative_id: '授权代表身份证号',
  authorized_representative: '授权代表',
  signature_date: '签署日期',
  delivery_period: '交货期承诺',
  warranty_period: '质保期承诺',
  bid_validity_days: '投标有效期',
  tax_rate: '税率',
  product_models: '产品规格型号',
  technical_parameter_summary: '技术参数表候选摘要',
  technical_deviation_candidates: '技术偏差表候选',
  taichang_parameter_match_summary: '泰昌参数佐证摘要',
};

function toCustomerText(value?: string | null): string {
  if (!value) return '-';
  return Object.entries(internalTokenLabels)
    .sort(([left], [right]) => right.length - left.length)
    .reduce((text, [token, label]) => text.split(token).join(label), value);
}

function emptyText(text: string): JSX.Element {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={text} />;
}

function actionTone(item: FormalCheckItem): 'primary' | 'default' {
  return item.status === 'blocked' ? 'primary' : 'default';
}

export function FormalCheckPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const projectIdParam = searchParams.get('projectId');
  const [projectId, setProjectId] = useState<string | null>(projectIdParam);
  const [report, setReport] = useState<FormalCheckReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [activeCategory, setActiveCategory] = useState('全部分类');
  const [activeStatus, setActiveStatus] = useState<FormalCheckStatus | '全部状态'>('全部状态');
  const [activeSeverity, setActiveSeverity] = useState<FormalCheckItem['severity'] | '全部等级'>('全部等级');

  async function resolveProjectId(): Promise<string | null> {
    if (projectIdParam) return projectIdParam;
    const latest = await getLatestInterpretation();
    return latest.project?.id || null;
  }

  async function load(options?: { reset?: boolean }): Promise<void> {
    try {
      if (options?.reset) {
        setHasLoaded(false);
        setReport(null);
      }
      setLoading(true);
      const resolvedProjectId = await resolveProjectId();
      setProjectId(resolvedProjectId);
      if (!resolvedProjectId) {
        setReport(null);
        return;
      }
      setReport(await getFormalCheckReport(resolvedProjectId));
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
      setHasLoaded(true);
    }
  }

  useEffect(() => {
    void load({ reset: true });
  }, [projectIdParam]);

  const categoryOptions = useMemo(() => [
    { label: '全部分类', value: '全部分类' },
    ...(report?.categorySummaries || []).map(item => ({ label: `${item.category}（${item.total}）`, value: item.category })),
  ], [report]);

  const filteredItems = useMemo(() => {
    let items = report?.items || [];
    if (activeCategory !== '全部分类') {
      items = items.filter(item => item.category === activeCategory);
    }
    if (activeStatus !== '全部状态') {
      items = items.filter(item => item.status === activeStatus);
    }
    if (activeSeverity !== '全部等级') {
      items = items.filter(item => item.severity === activeSeverity);
    }
    return items;
  }, [activeCategory, activeSeverity, activeStatus, report]);

  const metrics = [
    { title: '规则总数', value: report?.summary.totalRules || 0, desc: report?.ruleSetName || '正式检查规则', icon: ClipboardCheck, colorClass: 'bg-blue-50 text-blue-600' },
    { title: '阻断项', value: report?.summary.blocked || 0, desc: '影响正式版导出', icon: FileWarning, colorClass: report?.summary.blocked ? 'bg-rose-50 text-rose-600' : 'bg-emerald-50 text-emerald-600' },
    { title: '需关注', value: report?.summary.warnings || 0, desc: '建议处理后再提交', icon: AlertTriangle, colorClass: 'bg-amber-50 text-amber-600' },
    { title: '人工确认', value: report?.summary.manualConfirm || 0, desc: '导出后或业务确认', icon: ShieldCheck, colorClass: 'bg-cyan-50 text-cyan-600' },
    { title: '条款覆盖率', value: `${report?.summary.compliancePercent || 0}%`, desc: `${report?.summary.complianceMissing || 0} 项待覆盖`, icon: CheckCircle2, colorClass: 'bg-violet-50 text-violet-600' },
  ];

  function handleItemAction(item: FormalCheckItem): void {
    if (!projectId || !item.action) return;
    const target = item.action.target || item.target || '';
    if (item.action.type === 'prefill') {
      navigate(`/prefill?projectId=${projectId}${target ? `&focus=${encodeURIComponent(target)}` : ''}`);
      return;
    }
    if (item.action.type === 'product_library') {
      navigate(`/products${target ? `?category=${encodeURIComponent(target)}` : ''}`);
      return;
    }
    if (item.action.type === 'qualification_library') {
      navigate(`/qualification${target ? `?category=${encodeURIComponent(target)}` : ''}`);
      return;
    }
    navigate(`/bid-editor?projectId=${projectId}${target ? `&sectionId=${encodeURIComponent(target)}` : ''}`);
  }

  const columns: ColumnsType<FormalCheckItem> = [
    {
      title: '检查项',
      dataIndex: 'title',
      width: 280,
      render: (_, item) => (
        <div className="formal-check-title-cell">
          <strong>{item.title}</strong>
          <span>{item.description}</span>
          <div className="mt-2 flex flex-wrap gap-1">
            <Tag className="m-0">{item.id}</Tag>
            <Tag color={severityColor[item.severity]} className="m-0">{severityLabel[item.severity]}</Tag>
            <Tag color={statusColor[item.status]} className="m-0">{item.statusLabel}</Tag>
          </div>
        </div>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      width: 110,
      render: value => <Tag color="purple" className="m-0 whitespace-normal">{value}</Tag>,
    },
    {
      title: '证据',
      dataIndex: 'evidence',
      render: value => <Typography.Paragraph className="formal-check-long-text m-0">{toCustomerText(value)}</Typography.Paragraph>,
    },
    {
      title: '来源',
      width: 190,
      render: (_, item) => (
        <div className="formal-check-source">
          <strong>{toCustomerText(item.sourceLevel)}</strong>
          <span>{toCustomerText(item.sourceRef)}</span>
        </div>
      ),
    },
    {
      title: '处理路径',
      width: 160,
      fixed: 'right',
      render: (_, item) => (
        <div className="formal-check-action-cell">
          <Button
            size="small"
            type={actionTone(item)}
            icon={<ArrowRight size={14} />}
            disabled={!projectId || !item.action}
            onClick={() => handleItemAction(item)}
          >
            {item.action?.label || '去处理'}
          </Button>
          <span>{toCustomerText(item.action?.description || item.suggestion)}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="formal-check-shell">
      <ModuleHeader
        title="正式检查"
        description="正式导出前检查投标文件硬伤、客户确认字段、资料边界和导出成品风险；阻断项未清零时仅允许草稿版导出。"
        actions={
          <>
            <Button icon={<RefreshCw size={16} />} loading={loading} onClick={() => load()}>刷新检查</Button>
            <Button disabled={!projectId} onClick={() => projectId && navigate(`/prefill?projectId=${projectId}`)}>投标确认</Button>
            <Button type="primary" disabled={!projectId} onClick={() => projectId && navigate(`/bid-editor?projectId=${projectId}`)}>进入编制</Button>
          </>
        }
      />

      {report ? (
        <>
          <Alert
            type={report.summary.canFormalExport ? 'success' : 'warning'}
            showIcon
            message={report.summary.formalExportLabel}
            description={report.summary.canFormalExport
              ? '当前未发现阻断正式导出的检查项。正式导出后仍需执行 DOCX 成品复验。'
              : `当前存在 ${report.summary.blocked} 个阻断项，只允许导出草稿版。正式投标前请先处理阻断项并重新检查。`}
          />

          <MetricCards items={metrics} />

          <section className="panel-card">
            <div className="formal-check-meta">
              <div>
                <span>项目</span>
                <strong>{report.project?.project_name || '未命名项目'}</strong>
              </div>
              <div>
                <span>规则集</span>
                <strong>{toCustomerText(report.ruleSetName)}</strong>
              </div>
              <div>
                <span>生成时间</span>
                <strong>{formatDateTime(report.generatedAt)}</strong>
              </div>
            </div>
          </section>

          <section className="panel-card">
            <div className="mb-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div>
                <h2 className="panel-title mb-1">检查项明细</h2>
                <p className="m-0 text-sm font-semibold leading-6 text-slate-500">
                  第一版规则优先覆盖高频硬检查项。阻断项影响正式版导出，草稿版导出仍允许但必须保留草稿标记。
                </p>
              </div>
              <Space className="justify-start lg:justify-end" wrap>
                <Select value={activeCategory} options={categoryOptions} className="w-52" onChange={setActiveCategory} />
                <Select
                  value={activeStatus}
                  className="w-36"
                  onChange={setActiveStatus}
                  options={[
                    { label: '全部状态', value: '全部状态' },
                    { label: '阻断', value: 'blocked' },
                    { label: '需关注', value: 'warning' },
                    { label: '人工确认', value: 'manual_confirm' },
                    { label: '已通过', value: 'passed' },
                    { label: '不适用', value: 'not_applicable' },
                  ]}
                />
                <Select
                  value={activeSeverity}
                  className="w-32"
                  onChange={setActiveSeverity}
                  options={[
                    { label: '全部等级', value: '全部等级' },
                    { label: '阻断', value: 'blocker' },
                    { label: '高', value: 'high' },
                    { label: '中', value: 'medium' },
                    { label: '低', value: 'low' },
                  ]}
                />
              </Space>
            </div>
            <div className="bounded-table formal-check-table">
              <Table
                rowKey="id"
                size="small"
                columns={columns}
                dataSource={filteredItems}
                pagination={{ pageSize: 12, showTotal: total => `共 ${total} 项` }}
                locale={{ emptyText: emptyText('当前筛选条件下暂无检查项') }}
                scroll={{ x: 1160 }}
                expandable={{
                  expandedRowRender: item => (
                    <div className="formal-check-evidence-chain">
                      {(item.evidenceChain?.length ? item.evidenceChain : [
                        { label: '当前证据', value: item.evidence || '-' },
                        { label: '处理建议', value: item.suggestion || '-' },
                      ]).map(node => (
                        <div key={node.label}>
                          <strong>{node.label}</strong>
                          <span>{toCustomerText(node.value)}</span>
                        </div>
                      ))}
                    </div>
                  ),
                  rowExpandable: item => Boolean(item.evidence || item.suggestion || item.evidenceChain?.length),
                }}
              />
            </div>
          </section>

          <section className="panel-card">
            <h2 className="panel-title">规则来源说明</h2>
            <ul className="m-0 grid gap-2 pl-5 text-sm font-semibold leading-6 text-slate-600">
              {report.sourceNotes.map(note => <li key={note}>{toCustomerText(note)}</li>)}
            </ul>
          </section>
        </>
      ) : loading && !hasLoaded ? (
        <section className="panel-card formal-check-loading-card">
          <Skeleton active paragraph={{ rows: 5 }} title={{ width: 180 }} />
        </section>
      ) : (
        <section className="panel-card">
          {emptyText(projectId ? '当前项目暂无正式检查报告' : '暂无可用项目，请先上传并解析招标文件')}
        </section>
      )}
    </div>
  );
}
