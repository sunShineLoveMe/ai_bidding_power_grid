import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Descriptions, Drawer, Dropdown, Empty, List, Progress, Space, Table, Tabs, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { AlertTriangle, BrainCircuit, CheckCircle2, ClipboardCheck, Database, Eye, FileSearch, FileText, ListChecks, MoreHorizontal, RefreshCw, ShieldAlert, XCircle } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { generateAIInterpretation, getComplianceCheck, getInterpretation, getLatestInterpretation } from '../../api/bidProject';
import { MetricCards } from '../../components/common/MetricCards';
import { ModuleHeader } from '../../components/common/ModuleHeader';
import type {
  ChapterSuggestion,
  BidOutline,
  ComplianceReport,
  ComplianceRow,
  DocumentChunk,
  AIInterpretationReport,
  InterpretationResponse,
  InterpretationReport,
  MinerUQuality,
  RequirementItem,
  RiskItem,
  ScoringItem,
} from '../../types/interpretation';

const priorityColor: Record<string, string> = {
  high: 'red',
  medium: 'orange',
  low: 'blue',
};

const riskColor: Record<string, string> = {
  high: 'red',
  medium: 'orange',
  low: 'blue',
};

type SourceTrace = {
  title: string;
  category: string;
  sourcePage?: number | null;
  sourceSection?: string | null;
  sourceText?: string | null;
};

function pageText(page?: number | null): string {
  return page ? `第 ${page} 页` : '-';
}

function emptyText(description: string): JSX.Element {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={description} />;
}

function asReport(meta: Record<string, unknown>): InterpretationReport {
  return (meta.interpretation_report || {}) as InterpretationReport;
}

function asQuality(meta: Record<string, unknown>): MinerUQuality {
  return (meta.mineru_quality || {}) as MinerUQuality;
}

function asAIReport(meta: Record<string, unknown>): AIInterpretationReport | null {
  return (meta.ai_report || null) as AIInterpretationReport | null;
}

function asBidOutline(meta: Record<string, unknown>): BidOutline | null {
  return (meta.bid_outline || null) as BidOutline | null;
}

function formatDateTime(isoString?: string | null): string {
  if (!isoString) return '-';
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return isoString;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function TextList({ title, items }: { title: string; items?: string[] }): JSX.Element {
  return (
    <section className="report-section">
      <h3>{title}</h3>
      {items?.length ? (
        <ul>
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无内容" />
      )}
    </section>
  );
}

function SourceButton({ onClick }: { onClick: () => void }): JSX.Element {
  return (
    <Button type="link" size="small" icon={<Eye size={14} />} onClick={onClick}>
      依据
    </Button>
  );
}

export function InterpretationPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const projectIdParam = searchParams.get('projectId');
  const [data, setData] = useState<InterpretationResponse | null>(null);
  const [complianceReport, setComplianceReport] = useState<ComplianceReport | null>(null);
  const [generatingAI, setGeneratingAI] = useState(false);
  const [generatingOutline, setGeneratingOutline] = useState(false);
  const [sourceTrace, setSourceTrace] = useState<SourceTrace | null>(null);
  const [advancedPanel, setAdvancedPanel] = useState<'chunks' | 'mineru' | null>(null);

  async function load(): Promise<void> {
    try {
      const result = projectIdParam ? await getInterpretation(projectIdParam) : await getLatestInterpretation();
      setData(result);
      if (result.project?.id) {
        try {
          setComplianceReport(await getComplianceCheck(result.project.id));
        } catch (error) {
          setComplianceReport(null);
        }
      } else {
        setComplianceReport(null);
      }
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      message.error(reason);
    }
  }

  useEffect(() => {
    void load();
  }, [projectIdParam]);

  const projectMeta = data?.analysis?.project_meta || {};
  const report = asReport(projectMeta);
  const aiReport = asAIReport(projectMeta);
  const bidOutline = asBidOutline(projectMeta);
  const bidOutlineChapterCount = bidOutline?.chapters?.length
    || (bidOutline?.volumes || []).reduce((sum, volume) => sum + (volume.chapters?.length || 0), 0);
  const mineruQuality = asQuality(projectMeta);
  const relatedChunks = useMemo(() => {
    if (!sourceTrace?.sourcePage || !data?.documentChunks.length) {
      return [];
    }
    return data.documentChunks.filter(chunk => chunk.source_page === sourceTrace.sourcePage).slice(0, 8);
  }, [data?.documentChunks, sourceTrace?.sourcePage]);

  const complianceRows = complianceReport?.rows || [];
  const complianceSummary = complianceReport?.summary || {
    metricName: '条款响应覆盖率',
    scopeNote: '基于招标条款与当前章节/正文的响应追踪结果，不等同于最终 Word 标书合规结论。',
    total: 0,
    covered: 0,
    partial: 0,
    missing: 0,
    percent: 0,
    highRiskMissing: 0,
  };

  const metrics = useMemo(
    () => [
      { title: '要求条款', value: data?.requirements.length ?? 0, desc: '资格/商务/技术/文件', icon: ListChecks, colorClass: 'bg-blue-50 text-blue-600', tooltip: '从招标文件中抽取的资格要求、商务要求、技术要求和文件格式要求，用于后续章节大纲、正文生成和条款响应追踪。' },
      { title: '风险条款', value: data?.risks.length ?? 0, desc: '否决/无效/合规风险', icon: ShieldAlert, colorClass: 'bg-rose-50 text-rose-600', tooltip: '从招标文件中识别的废标、否决、无效投标和关键合规风险。该数量越高，越需要优先逐条确认响应。' },
      { title: '评分项', value: data?.scoringItems.length ?? 0, desc: '评分办法初步拆解', icon: ClipboardCheck, colorClass: 'bg-emerald-50 text-emerald-600', tooltip: '从评分办法中拆解出的得分点。后续标书正文应围绕高分项补充施工细节、证明材料、页码索引和可量化承诺。' },
      { title: '条款响应率', value: `${complianceSummary.percent}%`, desc: `${complianceSummary.missing} 项未响应 / ${complianceSummary.highRiskMissing || 0} 项高风险`, icon: CheckCircle2, colorClass: complianceSummary.missing ? 'bg-amber-50 text-amber-600' : 'bg-emerald-50 text-emerald-600', tooltip: complianceSummary.scopeNote || '基于招标条款、评分项、风险项与当前章节映射/正文片段的响应追踪结果，不等同于最终 Word 标书合规结论。' },
      { title: '章节大纲', value: bidOutlineChapterCount, desc: `${bidOutline?.volumes?.length || 0} 个分册`, icon: FileText, colorClass: 'bg-violet-50 text-violet-600', tooltip: '当前项目已生成的标书章节数量和分册数量。章节大纲是正文生成、条款响应和分册导出的基础。' },
    ],
    [bidOutlineChapterCount, bidOutline?.volumes?.length, complianceSummary.highRiskMissing, complianceSummary.missing, complianceSummary.percent, data],
  );

  const complianceColumns: ColumnsType<ComplianceRow> = [
    { title: '类别', dataIndex: 'category', width: 92, render: value => <Tag color={value === '风险项' ? 'red' : value === '评分项' ? 'green' : 'blue'}>{value}</Tag> },
    { title: '重要性', dataIndex: 'importance', width: 92, render: value => <Tag color={riskColor[String(value)] || priorityColor[String(value)] || 'default'}>{value || '-'}</Tag> },
    { title: '检查内容', dataIndex: 'content', ellipsis: true },
    {
      title: '覆盖状态',
      dataIndex: 'status',
      width: 110,
      render: value => {
        if (value === 'covered') return <Tag color="green">已覆盖</Tag>;
        if (value === 'partial') return <Tag color="orange">待补强</Tag>;
        return <Tag color="red">未覆盖</Tag>;
      },
    },
    { title: '对应章节', dataIndex: 'matchedChapter', width: 210, ellipsis: true, render: value => value || '需补充章节/正文' },
    { title: '页码', dataIndex: 'sourcePage', width: 78, render: pageText },
    {
      title: '依据',
      width: 78,
      render: (_, record) => (
        <SourceButton
          onClick={() => openSourceTrace({
            title: record.content,
            category: record.category,
            sourcePage: record.sourcePage,
            sourceSection: record.matchedChapter || '合规检查',
            sourceText: record.sourceText || record.content,
          })}
        />
      ),
    },
  ];

  function openSourceTrace(trace: SourceTrace): void {
    setSourceTrace(trace);
  }

  const requirementColumns: ColumnsType<RequirementItem> = [
    { title: '类型', dataIndex: 'requirement_type', width: 98, render: value => <Tag color="blue">{value || '要求'}</Tag> },
    { title: '优先级', dataIndex: 'priority', width: 82, render: value => <Tag color={priorityColor[String(value)] || 'default'}>{value || '-'}</Tag> },
    { title: '内容', dataIndex: 'content', ellipsis: true },
    { title: '章节', dataIndex: 'source_section', width: 160, ellipsis: true },
    { title: '页码', dataIndex: 'source_page', width: 78, render: pageText },
    {
      title: '原文',
      width: 78,
      render: (_, record) => (
        <SourceButton
          onClick={() => openSourceTrace({
            title: record.content || record.title || '要求条款',
            category: '要求条款',
            sourcePage: record.source_page,
            sourceSection: record.source_section,
            sourceText: record.source_text || record.content,
          })}
        />
      ),
    },
  ];

  const riskColumns: ColumnsType<RiskItem> = [
    { title: '等级', dataIndex: 'risk_level', width: 82, render: value => <Tag color={riskColor[String(value)] || 'default'}>{value || '-'}</Tag> },
    { title: '类型', dataIndex: 'risk_type', width: 120, ellipsis: true },
    { title: '风险内容', dataIndex: 'content', ellipsis: true },
    { title: '处理建议', dataIndex: 'action', width: 220, ellipsis: true },
    { title: '页码', dataIndex: 'source_page', width: 78, render: pageText },
    {
      title: '原文',
      width: 78,
      render: (_, record) => (
        <SourceButton
          onClick={() => openSourceTrace({
            title: record.content || '风险项',
            category: '风险项',
            sourcePage: record.source_page,
            sourceSection: record.source_section,
            sourceText: record.source_text || record.content,
          })}
        />
      ),
    },
  ];

  const scoringColumns: ColumnsType<ScoringItem> = [
    { title: '分类', dataIndex: 'category', width: 100 },
    { title: '评分项', dataIndex: 'item', ellipsis: true },
    { title: '分值', dataIndex: 'score', width: 76, render: value => (value ? `${value} 分` : '-') },
    { title: '响应建议', dataIndex: 'response_suggestion', width: 260, ellipsis: true },
    { title: '页码', dataIndex: 'source_page', width: 78, render: pageText },
    {
      title: '原文',
      width: 78,
      render: (_, record) => (
        <SourceButton
          onClick={() => openSourceTrace({
            title: record.item || record.requirement || '评分项',
            category: '评分项',
            sourcePage: record.source_page,
            sourceSection: record.source_section,
            sourceText: record.source_text || record.requirement || record.item,
          })}
        />
      ),
    },
  ];

  const chapterColumns: ColumnsType<ChapterSuggestion> = [
    { title: '建议章节', dataIndex: 'chapter_title', ellipsis: true },
    { title: '优先级', dataIndex: 'priority', width: 88, render: value => <Tag color={priorityColor[String(value)] || 'default'}>{value || '-'}</Tag> },
    { title: '建议原因', dataIndex: 'reason', width: 360, ellipsis: true },
  ];

  const chunkColumns: ColumnsType<DocumentChunk> = [
    { title: '序号', dataIndex: 'chunk_index', width: 76 },
    { title: '章节', dataIndex: 'source_section', width: 180, ellipsis: true },
    { title: '页码', dataIndex: 'source_page', width: 78, render: pageText },
    { title: '内容片段', dataIndex: 'content', ellipsis: true },
    {
      title: '查看',
      width: 78,
      render: (_, record) => (
        <SourceButton
          onClick={() => openSourceTrace({
            title: `原文分片 #${record.chunk_index}`,
            category: '原文分片',
            sourcePage: record.source_page,
            sourceSection: record.source_section,
            sourceText: record.content,
          })}
        />
      ),
    },
  ];

  const suspiciousColumns: ColumnsType<NonNullable<MinerUQuality['suspicious_blocks']>[number]> = [
    { title: '页码', dataIndex: 'page', width: 76, render: pageText },
    { title: '类型', dataIndex: 'type', width: 90 },
    { title: '原因', dataIndex: 'reason', width: 120 },
    { title: '片段', dataIndex: 'text', ellipsis: true },
  ];

  async function generateAIReport(): Promise<void> {
    if (!data?.project?.id) {
      message.warning('当前没有可生成 AI 解读的项目');
      return;
    }
    setGeneratingAI(true);
    try {
      await generateAIInterpretation(data.project.id);
      message.success('AI 深度解读已生成');
      await load();
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      message.error(reason);
    } finally {
      setGeneratingAI(false);
    }
  }

  async function generateOutline(): Promise<void> {
    if (!data?.project?.id) {
      message.warning('当前没有可生成章节大纲的项目');
      return;
    }
    setGeneratingOutline(true);
    try {
      navigate(`/bid-editor?projectId=${data.project.id}&autoGenerate=outline`);
    } finally {
      setGeneratingOutline(false);
    }
  }

  function renderAdvancedContent(): JSX.Element | null {
    if (advancedPanel === 'chunks') {
      return (
        <Table
          rowKey="id"
          size="small"
          pagination={{ pageSize: 8 }}
          columns={chunkColumns}
          dataSource={data?.documentChunks || []}
          className="compact-table"
          locale={{ emptyText: emptyText('暂无原文分片') }}
        />
      );
    }

    if (advancedPanel === 'mineru') {
      return (
        <div className="mineru-check-grid">
          <section className="quality-card">
            <div className="quality-score">
              <Progress type="circle" percent={mineruQuality.quality_score ?? 0} size={92} />
              <div>
                <h3>解析质量分</h3>
                <p>用于快速判断 OCR、分片、页码和结构识别是否需要人工复核。</p>
              </div>
            </div>
            <Descriptions size="small" column={2} bordered>
              <Descriptions.Item label="Markdown 字符">{mineruQuality.markdown_chars ?? 0}</Descriptions.Item>
              <Descriptions.Item label="内容块">{mineruQuality.content_blocks ?? 0}</Descriptions.Item>
              <Descriptions.Item label="页数">{mineruQuality.page_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="平均块长">{mineruQuality.avg_text_block_length ?? 0}</Descriptions.Item>
            </Descriptions>
          </section>
          <section className="quality-card">
            <h3>校验清单</h3>
            <List
              size="small"
              dataSource={mineruQuality.checklist || []}
              renderItem={item => (
                <List.Item>
                  <span className="inline-flex items-center gap-2 text-sm font-bold text-slate-700">
                    {item.ok ? <CheckCircle2 size={16} className="text-emerald-500" /> : <XCircle size={16} className="text-rose-500" />}
                    {item.label}
                  </span>
                </List.Item>
              )}
            />
          </section>
          <section className="quality-card">
            <h3>内容块类型</h3>
            <div className="quality-tags">
              {Object.entries(mineruQuality.block_type_counts || {}).map(([name, count]) => (
                <Tag key={name} color="blue">{name}: {count}</Tag>
              ))}
            </div>
          </section>
          <section className="quality-card">
            <h3>解析产物路径</h3>
            <div className="artifact-list">
              {Object.entries(mineruQuality.artifacts || {}).map(([name, value]) => (
                <div key={name}>
                  <strong>{name}</strong>
                  <span>{value || '-'}</span>
                </div>
              ))}
            </div>
          </section>
          <section className="quality-card quality-wide">
            <h3>可疑解析片段</h3>
            <Table
              rowKey={(_, index) => String(index)}
              size="small"
              pagination={{ pageSize: 6 }}
              columns={suspiciousColumns}
              dataSource={mineruQuality.suspicious_blocks || []}
              className="compact-table"
              locale={{ emptyText: emptyText('未发现明显可疑片段') }}
            />
          </section>
        </div>
      );
    }

    return null;
  }

  return (
    <div className="interpretation-shell">
      <ModuleHeader
        title="招标项目"
        description="集中查看当前招标文件的项目概况、资格要求、评分办法、风险检查和章节建议。"
        actions={
          <>
            <Button icon={<BrainCircuit size={16} />} loading={generatingAI} disabled={!data?.analysis} onClick={() => void generateAIReport()}>
              生成AI解读
            </Button>
            <Button icon={<FileText size={16} />} loading={generatingOutline} disabled={!data?.analysis} onClick={() => void generateOutline()}>
              生成章节大纲
            </Button>
            <Dropdown
              disabled={!data?.analysis}
              menu={{
                items: [
                  { key: 'chunks', label: '查看原文分片', icon: <Database size={14} /> },
                  { key: 'mineru', label: 'MinerU 解析校验', icon: <FileSearch size={14} /> },
                ],
                onClick: info => setAdvancedPanel(info.key as 'chunks' | 'mineru'),
              }}
            >
              <Button icon={<MoreHorizontal size={16} />}>高级信息</Button>
            </Dropdown>
            <Button type="primary" icon={<RefreshCw size={16} />} onClick={() => void load()}>
              刷新解读
            </Button>
          </>
        }
      />
      <MetricCards items={metrics} />

      {!data?.analysis ? (
        <section className="panel-card">
          <Alert
            type="info"
            showIcon
            icon={<FileSearch size={18} />}
            message="暂无可展示的招标解读"
            description="请先上传招标文件并等待 MinerU 解析、结构化落库完成。"
          />
        </section>
      ) : (
        <>
          <section className="panel-card">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="panel-title mb-0">项目概况</h2>
              <Space size={6}>
                <Tag color="blue">{data.project?.status || '已解析'}</Tag>
                <Tag color="purple">{String(projectMeta.tender_no || data.project?.project_no || '暂无编号')}</Tag>
              </Space>
            </div>
            <Descriptions size="small" column={4} bordered>
              <Descriptions.Item label="项目名称" span={2}>
                {String(projectMeta.project_name || data.project?.project_name || '-')}
              </Descriptions.Item>
              <Descriptions.Item label="招标编号">{String(projectMeta.tender_no || data.project?.project_no || '-')}</Descriptions.Item>
              <Descriptions.Item label="项目类型">{String(data.project?.project_type || projectMeta.document_type || '-')}</Descriptions.Item>
              <Descriptions.Item label="招标人">{data.project?.tender_unit || '-'}</Descriptions.Item>
              <Descriptions.Item label="代理机构">{data.project?.agency || '-'}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{formatDateTime(data.project?.created_at)}</Descriptions.Item>
              <Descriptions.Item label="解读摘要" span={4}>
                {data.analysis.summary || '-'}
              </Descriptions.Item>
            </Descriptions>
          </section>

          <section className="panel-card interpretation-main">
            <Tabs
              size="small"
              items={[
                {
                  key: 'report',
                  label: '解读总览',
                  children: (
                    <div className="report-grid">
                      <section className="report-hero">
                        <div>
                          <span>{aiReport ? '大模型深度解读' : '规则版解读报告'}</span>
                          <h2>{aiReport?.project_brief?.project_name || report.title || String(projectMeta.project_name || data.project?.project_name || '招标文件')}</h2>
                          <p>{aiReport ? aiReport.project_brief?.core_conclusion || 'AI 已基于结构化条款生成业务解读。' : '当前报告基于 MinerU 解析结果和规则抽取生成，点击“生成AI深度解读”可获得更连贯的业务报告。'}</p>
                        </div>
                      </section>
                      {aiReport ? (
                        <>
                          <section className="report-section report-wide">
                            <h3>一页式业务摘要</h3>
                            <ul>
                              {(aiReport.executive_summary || []).map((item, index) => <li key={`summary-${index}`}>{item}</li>)}
                            </ul>
                          </section>
                          <section className="report-section">
                            <h3>项目关键信息</h3>
                            <div className="brief-list">
                              <div><strong>项目名称</strong><span>{aiReport.project_brief?.project_name || '-'}</span></div>
                              <div><strong>招标编号</strong><span>{aiReport.project_brief?.tender_no || '-'}</span></div>
                              <div><strong>采购范围</strong><span>{aiReport.project_brief?.procurement_scope || '需人工复核'}</span></div>
                            </div>
                          </section>
                          <section className="report-section">
                            <h3>关键时间/节点</h3>
                            <ul>
                              {(aiReport.project_brief?.key_deadlines || []).map((item, index) => <li key={`deadline-${index}`}>{item}</li>)}
                            </ul>
                          </section>
                          <section className="report-section report-wide">
                            <h3>资格符合性核查</h3>
                            <div className="ai-card-list">
                              {(aiReport.qualification_review || []).map((item, index) => (
                                <article key={`qualification-${index}`} className="ai-evidence-card">
                                  <div>
                                    <Tag color={item.judgement === '风险较高' ? 'red' : 'blue'}>{item.judgement || '需复核'}</Tag>
                                    <strong>{item.requirement || '资格要求'}</strong>
                                  </div>
                                  <p>{item.evidence || '暂无原文依据摘要'}</p>
                                  <footer>
                                    <span>{pageText(item.source_page)}</span>
                                    <Button
                                      size="small"
                                      icon={<Eye size={14} />}
                                      onClick={() => openSourceTrace({
                                        title: item.requirement || '资格符合性核查',
                                        category: 'AI资格核查',
                                        sourcePage: item.source_page,
                                        sourceSection: 'AI 解读引用',
                                        sourceText: item.evidence || item.action || item.requirement,
                                      })}
                                    >
                                      查看依据
                                    </Button>
                                  </footer>
                                  <small>动作：{item.action || '需人工确认'}</small>
                                </article>
                              ))}
                            </div>
                          </section>
                          <section className="report-section report-wide">
                            <h3>评分高分策略</h3>
                            <div className="ai-card-list">
                              {(aiReport.scoring_strategy || []).map((item, index) => (
                                <article key={`scoring-${index}`} className="ai-evidence-card">
                                  <div>
                                    <Tag color="green">{item.score ? `${item.score} 分` : '分值待复核'}</Tag>
                                    <strong>{item.scoring_point || '评分项'}</strong>
                                  </div>
                                  <p>{item.strategy || '-'}</p>
                                  <p className="muted-text">材料：{(item.supporting_materials || []).join('、') || '需人工复核'}</p>
                                  <footer>
                                    <span>{pageText(item.source_page)}</span>
                                    <Button
                                      size="small"
                                      icon={<Eye size={14} />}
                                      onClick={() => openSourceTrace({
                                        title: item.scoring_point || '评分高分策略',
                                        category: 'AI评分策略',
                                        sourcePage: item.source_page,
                                        sourceSection: 'AI 解读引用',
                                        sourceText: item.evidence || item.strategy || item.scoring_point,
                                      })}
                                    >
                                      查看依据
                                    </Button>
                                  </footer>
                                </article>
                              ))}
                            </div>
                          </section>
                          <section className="report-section report-wide">
                            <h3>废标/否决风险</h3>
                            <div className="ai-card-list">
                              {(aiReport.risk_warnings || []).map((item, index) => (
                                <article key={`risk-${index}`} className="ai-evidence-card">
                                  <div>
                                    <Tag color={riskColor[item.risk_level || 'medium'] || 'orange'}>{item.risk_level || 'medium'}</Tag>
                                    <strong>{item.risk || '风险项'}</strong>
                                  </div>
                                  <p>影响：{item.impact || '-'}</p>
                                  <p>应对：{item.mitigation || '-'}</p>
                                  <footer>
                                    <span>{pageText(item.source_page)}</span>
                                    <Button
                                      size="small"
                                      icon={<Eye size={14} />}
                                      onClick={() => openSourceTrace({
                                        title: item.risk || '废标/否决风险',
                                        category: 'AI风险提示',
                                        sourcePage: item.source_page,
                                        sourceSection: 'AI 解读引用',
                                        sourceText: item.evidence || item.impact || item.mitigation || item.risk,
                                      })}
                                    >
                                      查看依据
                                    </Button>
                                  </footer>
                                </article>
                              ))}
                            </div>
                          </section>
                          <section className="report-section">
                            <h3>投标文件编制建议</h3>
                            <ul>
                              {(aiReport.document_plan || []).map((item, index) => (
                                <li key={`plan-${index}`}>
                                  {item.chapter}：{item.purpose || '-'}；重点：{(item.key_points || []).join('、') || '-'}
                                </li>
                              ))}
                            </ul>
                          </section>
                          <section className="report-section">
                            <h3>材料准备清单</h3>
                            <ul>
                              {(aiReport.material_checklist || []).map((item, index) => (
                                <li key={`material-${index}`}>
                                  {item.material}（{item.category || '其他'}）；负责人：{item.owner || '需确认'}；说明：{item.note || '-'}
                                </li>
                              ))}
                            </ul>
                          </section>
                          <TextList title="下一步动作" items={aiReport.next_actions} />
                        </>
                      ) : (
                        <>
                          <TextList title="一页式摘要" items={report.executive_summary} />
                          <TextList title="资格核查重点" items={report.qualification_focus} />
                          <TextList title="商务响应重点" items={report.business_focus} />
                          <TextList title="技术响应重点" items={report.technical_focus} />
                          <TextList title="评分响应策略" items={report.scoring_strategy} />
                          <TextList title="重点风险提示" items={report.risk_focus} />
                          <TextList title="建议投标章节" items={report.chapter_plan} />
                          <TextList title="下一步动作" items={report.next_actions} />
                        </>
                      )}
                    </div>
                  ),
                },
                {
                  key: 'compliance',
                  label: '条款响应',
                  children: (
                    <div className="space-y-4">
                      <Alert
                        type={complianceSummary.missing ? 'warning' : 'success'}
                        showIcon
                        message={`${complianceSummary.metricName || '条款响应覆盖率'} ${complianceSummary.percent}%`}
                        description={`${complianceSummary.scopeNote || '该指标用于追踪招标条款与当前章节/正文的响应关系，不等同于最终 Word 标书合规结论。'} 共检查 ${complianceSummary.total} 项，其中已响应 ${complianceSummary.covered} 项、待补强 ${complianceSummary.partial} 项、未响应 ${complianceSummary.missing} 项，高风险未响应 ${complianceSummary.highRiskMissing || 0} 项。`}
                      />
                      {complianceReport?.recommendations?.length ? (
                        <div className="rounded-md bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800">
                          {complianceReport.recommendations.map((item, index) => (
                            <p key={`compliance-rec-${index}`} className="mb-1 last:mb-0">{item}</p>
                          ))}
                        </div>
                      ) : null}
                      <Progress
                        percent={complianceSummary.percent}
                        status={complianceSummary.missing ? 'active' : 'success'}
                        strokeColor={complianceSummary.missing ? '#f59e0b' : '#22c55e'}
                      />
                      <Table
                        rowKey="id"
                        size="small"
                        pagination={{ pageSize: 10 }}
                        columns={complianceColumns}
                        dataSource={complianceRows}
                        className="compact-table"
                        locale={{ emptyText: emptyText('暂无可检查的合规项，请先完成招标文件解析和章节大纲生成') }}
                      />
                    </div>
                  ),
                },
                {
                  key: 'requirements',
                  label: '资格与要求',
                  children: (
                    <Table rowKey="id" size="small" pagination={{ pageSize: 10 }} columns={requirementColumns} dataSource={data.requirements} className="compact-table" locale={{ emptyText: emptyText('暂无要求条款') }} />
                  ),
                },
                {
                  key: 'risks',
                  label: (
                    <span className="inline-flex items-center gap-1">
                      <AlertTriangle size={14} />
                      风险检查
                    </span>
                  ),
                  children: <Table rowKey="id" size="small" pagination={{ pageSize: 10 }} columns={riskColumns} dataSource={data.risks} className="compact-table" locale={{ emptyText: emptyText('暂无风险项') }} />,
                },
                {
                  key: 'scoring',
                  label: '评分办法',
                  children: <Table rowKey="id" size="small" pagination={{ pageSize: 10 }} columns={scoringColumns} dataSource={data.scoringItems} className="compact-table" locale={{ emptyText: emptyText('暂无评分项') }} />,
                },
                {
                  key: 'chapters',
                  label: '章节建议',
                  children: <Table rowKey="id" size="small" pagination={{ pageSize: 10 }} columns={chapterColumns} dataSource={data.chapterSuggestions} className="compact-table" locale={{ emptyText: emptyText('暂无建议章节') }} />,
                },
              ]}
            />
          </section>

          <section className="panel-card interpretation-note">
            <Typography.Text strong>当前说明</Typography.Text>
            <Typography.Text type="secondary">
              当前解读已支持原文溯源。业务人员可从资格要求、风险检查、评分办法和解读总览中打开依据；原文分片与 MinerU 校验已收纳到右上角“高级信息”。
            </Typography.Text>
          </section>
        </>
      )}
      <Drawer
        title={advancedPanel === 'chunks' ? '原文分片' : 'MinerU 解析校验'}
        width={advancedPanel === 'mineru' ? 980 : 820}
        open={Boolean(advancedPanel)}
        onClose={() => setAdvancedPanel(null)}
      >
        {renderAdvancedContent()}
      </Drawer>
      <Drawer
        title="原文依据"
        width={640}
        open={Boolean(sourceTrace)}
        onClose={() => setSourceTrace(null)}
      >
        {sourceTrace ? (
          <div className="source-drawer">
            <Space size={8} wrap>
              <Tag color="blue">{sourceTrace.category}</Tag>
              <Tag>{pageText(sourceTrace.sourcePage)}</Tag>
              <Tag>{sourceTrace.sourceSection || '暂无章节'}</Tag>
            </Space>
            <h3>{sourceTrace.title}</h3>
            <section>
              <h4>直接依据</h4>
              <p>{sourceTrace.sourceText || '当前条目没有保存独立原文片段，请结合下方同页分片复核。'}</p>
            </section>
            <section>
              <h4>同页 MinerU 分片</h4>
              {relatedChunks.length ? (
                <List
                  size="small"
                  dataSource={relatedChunks}
                  renderItem={chunk => (
                    <List.Item>
                      <article className="chunk-preview">
                        <div>
                          <strong>#{chunk.chunk_index}</strong>
                          <span>{chunk.source_section || '未识别章节'}</span>
                        </div>
                        <p>{chunk.content}</p>
                      </article>
                    </List.Item>
                  )}
                />
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无同页分片" />
              )}
            </section>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
