import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Descriptions, Empty, Space, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ClipboardCheck, Database, FileWarning, RefreshCw, ShieldAlert } from 'lucide-react';
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
  if (value === null || value === undefined || value === '') return '-';
  if (Array.isArray(value)) {
    return value.map(item => {
      if (item && typeof item === 'object' && 'title' in item) {
        return String((item as { title?: string }).title || '');
      }
      return String(item);
    }).filter(Boolean).join('；') || '-';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

function emptyText(text: string): JSX.Element {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={text} />;
}

export function BidPrefillPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const projectIdParam = searchParams.get('projectId');
  const [projectId, setProjectId] = useState<string | null>(projectIdParam);
  const [report, setReport] = useState<BidPrefillReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeGroup, setActiveGroup] = useState('全部字段');

  async function resolveProjectId(): Promise<string | null> {
    if (projectIdParam) return projectIdParam;
    const latest = await getLatestInterpretation();
    return latest.project?.id || null;
  }

  async function load(): Promise<void> {
    try {
      setLoading(true);
      const resolvedProjectId = await resolveProjectId();
      setProjectId(resolvedProjectId);
      if (!resolvedProjectId) {
        setReport(null);
        return;
      }
      setReport(await getBidPrefillReport(resolvedProjectId));
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
      ...reportGroups.map(group => ({ name: group.name, count: group.fields.length })),
    ];
  }, [report]);

  const fields = useMemo(() => {
    if (!report) return [];
    if (activeGroup === '全部字段') return report.fields;
    return report.fields.filter(field => field.group === activeGroup);
  }, [activeGroup, report]);

  const columns: ColumnsType<BidPrefillField> = [
    { title: '字段', dataIndex: 'label', width: 170, fixed: 'left' },
    { title: '分组', dataIndex: 'group', width: 120, render: value => <Tag color="purple">{value}</Tag> },
    { title: '状态', dataIndex: 'status', width: 118, render: (_, record) => <Tag color={statusColor[record.status]}>{record.statusLabel}</Tag> },
    { title: '当前候选值', dataIndex: 'value', ellipsis: true, render: value => formatValue(value) },
    { title: '风险', dataIndex: 'riskLevel', width: 98, render: value => <Tag color={riskColor[value] || 'default'}>{value}</Tag> },
    { title: '来源规则', dataIndex: 'sourcePolicy', ellipsis: true },
    { title: '依据', width: 160, render: (_, record) => record.evidence?.sourceLabel || '-' },
  ];

  const gapColumns: ColumnsType<BidPrefillField> = [
    { title: '缺口字段', dataIndex: 'label', width: 150 },
    { title: '分组', dataIndex: 'group', width: 120 },
    { title: '状态', width: 110, render: (_, record) => <Tag color={statusColor[record.status]}>{record.statusLabel}</Tag> },
    { title: '处理要求', dataIndex: 'sourcePolicy', ellipsis: true },
  ];

  const metrics = [
    { title: '字段总数', value: report?.summary.totalFields || 0, desc: `schema ${report?.schemaVersion || '-'}`, icon: ClipboardCheck, colorClass: 'bg-blue-50 text-blue-600' },
    { title: '系统已识别', value: report?.summary.systemRecognized || 0, desc: '来自招标解析', icon: Database, colorClass: 'bg-cyan-50 text-cyan-600' },
    { title: '企业库带出', value: report?.summary.enterpriseLibrary || 0, desc: '来自知识/资信/产品库', icon: Database, colorClass: 'bg-emerald-50 text-emerald-600' },
    { title: '客户需填写', value: report?.summary.customerRequired || 0, desc: '报价/保证金/授权等', icon: ShieldAlert, colorClass: 'bg-rose-50 text-rose-600' },
    { title: '正式必填缺口', value: report?.summary.formalRequiredGaps || 0, desc: '导出门禁前应收口', icon: FileWarning, colorClass: 'bg-amber-50 text-amber-600' },
  ];

  return (
    <div className="module-shell relative">
      <ModuleHeader
        title="投标信息确认"
        description="生成正文前收口项目变量、企业资料候选和客户需确认缺口。当前为旁路只读确认，不自动覆盖正文。"
        actions={
          <>
            <Button icon={<RefreshCw size={16} />} loading={loading} onClick={load}>刷新报告</Button>
            <Button
              type="primary"
              disabled={!projectId}
              onClick={() => projectId && navigate(`/bid-editor?projectId=${projectId}`)}
            >
              进入正文编辑
            </Button>
          </>
        }
      />

      <Alert
        className="my-4"
        type="info"
        showIcon
        message="P1C-4 v1 只做字段确认和缺口报告"
        description="本页不会写入章节正文，不会触发变量替换，不影响 sectionsSnapshot DOCX 导出契约。报价、保证金、授权签章等客户决策字段必须人工确认。"
      />

      {report ? (
        <>
          <MetricCards items={metrics} />

          <section className="panel-card my-4">
            <Descriptions
              size="small"
              column={4}
              items={[
                { key: 'project', label: '项目', children: report.project?.project_name || '未命名项目' },
                { key: 'projectNo', label: '招标编号', children: report.project?.project_no || '-' },
                { key: 'generatedAt', label: '生成时间', children: report.generatedAt },
                { key: 'readonly', label: '接入方式', children: report.summary.readonlyFirst ? '旁路只读' : '可写入' },
              ]}
            />
          </section>

          <div className="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)]">
            <section className="panel-card">
              <h2 className="panel-title">字段分组</h2>
              <div className="grid gap-2">
                {groups.map(group => (
                  <button
                    key={group.name}
                    type="button"
                    className={`flex h-11 items-center justify-between rounded-lg px-3 text-left text-sm font-bold ${
                      activeGroup === group.name ? 'bg-blue-50 text-blue-600' : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
                    }`}
                    onClick={() => setActiveGroup(group.name)}
                  >
                    <span>{group.name}</span>
                    <Tag className="m-0">{group.count}</Tag>
                  </button>
                ))}
              </div>
            </section>

            <section className="panel-card min-w-0">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="panel-title mb-0">变量 schema v1</h2>
                <Typography.Text type="secondary">共 {fields.length} 个字段</Typography.Text>
              </div>
              <Table
                rowKey="key"
                size="small"
                columns={columns}
                dataSource={fields}
                loading={loading}
                scroll={{ x: 1120 }}
                pagination={{ pageSize: 12, showSizeChanger: false }}
                locale={{ emptyText: emptyText('暂无字段') }}
              />
            </section>
          </div>

          <section className="panel-card mt-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="panel-title mb-0">客户确认缺口报告</h2>
              <Space>
                <Tag color="red">客户需填写 {report.gapReport.customerRequiredFields.length}</Tag>
                <Tag color="orange">待人工确认 {report.gapReport.manualConfirmFields.length}</Tag>
              </Space>
            </div>
            <Table
              rowKey="key"
              size="small"
              columns={gapColumns}
              dataSource={report.gapReport.formalRequiredGaps}
              pagination={false}
              locale={{ emptyText: emptyText('当前没有正式必填缺口') }}
            />
          </section>

          <section className="panel-card mt-4">
            <h2 className="panel-title">预填来源规则</h2>
            <ul className="m-0 grid gap-2 pl-5 text-sm font-semibold leading-6 text-slate-600">
              {report.sourceRules.map(rule => <li key={rule}>{rule}</li>)}
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
