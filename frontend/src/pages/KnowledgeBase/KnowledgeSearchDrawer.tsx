import { Drawer, Input, Button, List, Typography, Image, message, Select, Space, Tag } from 'antd';
import { SearchOutlined, SendOutlined } from '@ant-design/icons';
import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { BrandMark } from '../../components/common/BrandMark';

const { Text } = Typography;

interface ImageMeta {
  url: string;
  alt: string;
}

interface SourceContext {
  content?: string;
  similarity?: number;
  metadata?: {
    doc_type?: string;
    doc_role?: string;
    source_org?: string;
    source_url?: string;
    source_file?: string;
    category_label?: string;
    category?: string;
    tags?: string;
    province?: string;
    batch_no?: string;
    package_code?: string;
    material_category?: string;
    ingestion_batch_id?: string;
    chunk_layer?: string;
    table_name?: string;
    row_number?: number;
  };
}

interface KnowledgeAsset {
  id?: string;
  title?: string;
  description?: string;
  category?: string;
  asset_type?: string;
  public_url?: string;
  source_url?: string;
  license?: string;
  attribution?: string;
  applicable_sections?: string[];
  applicable_volumes?: string[];
  tags?: string[];
  similarity?: number;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sourceQuery?: string;
  images?: ImageMeta[];
  sources?: SourceContext[];
  assets?: KnowledgeAsset[];
  followups?: string[];
  followupLoading?: boolean;
  streaming?: boolean;
  status?: string;
  clarification?: ClarificationPayload;
}

interface KnowledgeScope {
  seed_corpus: string;
  ingestion_batch_id?: string;
  province?: string;
  batch_no?: string;
  package_code?: string;
  material_category?: string;
  material_categories?: string[];
  doc_roles?: string[];
  documents?: number;
  label?: string;
}

interface ClarificationPayload {
  message: string;
  scopes?: KnowledgeScope[];
}

type ScenarioValue = 'qa' | 'writing' | 'compliance' | 'table';

const scenarioOptions: { label: string; value: ScenarioValue; description: string }[] = [
  { label: '问答', value: 'qa', description: '适合查条款、要求、说明位置' },
  { label: '写作参考', value: 'writing', description: '命中后回溯较完整 parent 上下文' },
  { label: '合规风险', value: 'compliance', description: '适合查否决、废标、实质性响应' },
  { label: '货物清单', value: 'table', description: '适合查物料编码、数量、交货方式' },
];

const docRoleLabel: Record<string, string> = {
  main_tender_file: '主招标文件',
  tender_notice: '招标公告',
  technical_spec: '技术规范',
  goods_list: '货物清单',
  contract_general_terms: '合同通用条款',
  contract_special_terms: '合同专用条款',
  bid_instructions: '投标注意事项',
  policy_regulation: '政策法规',
  sgcc_rule: '国网制度',
  standard_spec: '标准规范',
  self_phrase: '标准话术',
};

function sourceTitle(source: SourceContext): string {
  const meta = source.metadata || {};
  const sourceName = meta.source_org || meta.source_file || meta.category_label || meta.category || '企业知识库';
  return sourceName.split('/').pop() || sourceName;
}

function sourceDescription(source: SourceContext): string {
  const meta = source.metadata || {};
  return [
    meta.province,
    meta.package_code,
    meta.material_category,
    meta.doc_role ? docRoleLabel[meta.doc_role] || meta.doc_role : meta.doc_type,
    meta.table_name ? `${meta.table_name}${meta.row_number ? ` 第${meta.row_number}行` : ''}` : '',
    meta.tags,
  ].filter(Boolean).join(' · ') || '知识片段';
}

function previewText(content?: string): string {
  return (content || '').replace(/\s+/g, ' ').trim().slice(0, 120);
}

function assetImageMarkdown(asset: KnowledgeAsset, index: number): string {
  if (!asset.id) return '';
  const alt = (asset.title || `图片资产${index}`).replace(/[\[\]()]/g, '');
  return `\n\n![${alt}](/api/knowledge/assets/${asset.id}/file?variant=thumb)\n\n`;
}

function withInlineAssetImages(content: string, assets?: KnowledgeAsset[]): string {
  if (!content || !assets?.length) return content;

  const usedAssetIndexes = new Set<number>();
  const lines = content.split('\n');
  const output: string[] = [];

  for (const line of lines) {
    output.push(line);
    const matches = [...line.matchAll(/图片资产\s*([0-9]+(?:\s*[、,，]\s*[0-9]+)*)/g)];
    if (!matches.length) continue;

    const markdownSnippets: string[] = [];
    for (const match of matches) {
      const indexes = (match[1] || '')
        .split(/[、,，]/)
        .map(item => Number.parseInt(item.trim(), 10))
        .filter(Number.isFinite);

      for (const assetIndex of indexes) {
        const zeroBasedIndex = assetIndex - 1;
        const asset = assets[zeroBasedIndex];
        if (!asset?.id || usedAssetIndexes.has(assetIndex)) continue;
        const imageUrl = `/api/knowledge/assets/${asset.id}/file`;
        if (content.includes(imageUrl)) continue;
        const snippet = assetImageMarkdown(asset, assetIndex);
        if (snippet) {
          markdownSnippets.push(snippet);
          usedAssetIndexes.add(assetIndex);
        }
      }
    }

    if (markdownSnippets.length) {
      output.push(markdownSnippets.join(''));
    }
  }

  return output.join('\n');
}

function uniqueQuestions(questions: string[]): string[] {
  const seen = new Set<string>();
  return questions
    .map(question => question.trim())
    .filter(Boolean)
    .filter(question => {
      if (seen.has(question)) return false;
      seen.add(question);
      return true;
    })
    .slice(0, 3);
}

function buildFollowupQuestions(question: string, answer: string, assets?: KnowledgeAsset[], sources?: SourceContext[]): string[] {
  const text = `${question}\n${answer}\n${(assets || []).map(asset => `${asset.title || ''} ${asset.category || ''} ${(asset.tags || []).join(' ')}`).join('\n')}`;
  const candidates: string[] = [];

  const hasAssets = Boolean(assets?.length);
  const hasImages = hasAssets || /图片资产|配图|图片|附件|样张/.test(text);
  const hasQualification = /资质|资信|证书|营业执照|许可证|安全生产|社保|人员|项目经理|技术负责人/.test(text);
  const hasPerformance = /业绩|合同|中标|验收|类似项目/.test(text);
  const hasProduct = /产品|设备|参数|图册|闸门|水泵|水轮机|叶片|材料/.test(text);
  const hasRisk = /风险|废标|否决|缺失|不满足|不合规|补充/.test(text);

  if (hasImages) {
    candidates.push('这些图片分别适合放在标书哪些章节？');
    candidates.push('帮我筛选哪些图片可以插入正文，哪些只能作为附件或占位图。');
  }
  if (hasQualification) {
    candidates.push('帮我检查这些资信材料还缺哪些关键证明。');
    candidates.push('基于这些资信材料生成资格审查资料章节提纲。');
  }
  if (hasPerformance) {
    candidates.push('这些业绩材料需要补充哪些合同、中标或验收证明？');
  }
  if (hasProduct) {
    candidates.push('把这些产品资料整理成技术响应配图清单。');
  }
  if (hasRisk) {
    candidates.push('这些材料在投标时有哪些废标或否决风险？');
  }
  if (sources?.length) {
    candidates.push('请按标书人员可执行的方式整理成核查清单。');
  }

  candidates.push('把上面的内容整理成可直接放进标书的段落。');
  candidates.push('下一步我应该优先补充哪些企业资料？');

  return uniqueQuestions(candidates);
}

function scopeLabel(scope: KnowledgeScope): string {
  return scope.label || [scope.province, scope.batch_no, scope.package_code, scope.material_category].filter(Boolean).join(' / ') || '客户资料';
}

function scopeMetadata(scope?: KnowledgeScope | null): Record<string, string> | undefined {
  if (!scope) return undefined;
  const metadata: Record<string, string> = {
    seed_corpus: scope.seed_corpus || 'power_grid_customer_corpus',
  };
  if (scope.ingestion_batch_id) metadata.ingestion_batch_id = scope.ingestion_batch_id;
  if (scope.province) metadata.province = scope.province;
  if (scope.package_code) metadata.package_code = scope.package_code;
  return metadata;
}

export function KnowledgeSearchDrawer({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [scenario, setScenario] = useState<ScenarioValue>('qa');
  const [scopeKey, setScopeKey] = useState('auto');
  const [scopes, setScopes] = useState<KnowledgeScope[]>([]);

  useEffect(() => {
    if (!visible) return;
    fetch('/api/knowledge/scopes')
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error('加载知识库范围失败'))))
      .then((data) => setScopes(Array.isArray(data.customer_scopes) ? data.customer_scopes : []))
      .catch(() => setScopes([]));
  }, [visible]);

  const selectedScope = useMemo(() => {
    if (scopeKey === 'auto') return null;
    return scopes[Number(scopeKey)] || null;
  }, [scopeKey, scopes]);

  const guideQuestions = [
    '电网设备采购项目投标文件需要重点准备哪些资格材料？',
    '技术规范书响应和技术偏差表应该如何组织？',
    '根据现有知识库，电网投标最容易出现哪些废标或否决风险？',
  ];

  const handleSearch = async (presetQuery?: string, overrideScope?: KnowledgeScope | null) => {
    const currentQuery = (presetQuery || query).trim();
    if (!currentQuery) return;

    const userMessage: Message = { role: 'user', content: currentQuery };
    const assistantMessage: Message = {
      role: 'assistant',
      content: '',
      sourceQuery: currentQuery,
      status: '正在检索知识库资料...',
      streaming: true,
    };
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setQuery('');
    setLoading(true);

    try {
      const res = await fetch('/api/knowledge/search/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userMessage.content,
          scenario,
          return_parent: scenario === 'writing',
          metadata_filter: scopeMetadata(overrideScope === undefined ? selectedScope : overrideScope),
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error('检索请求失败');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let hasContent = false;
      let streamedAnswer = '';
      let retrievedAssets: KnowledgeAsset[] = [];
      let retrievedSources: SourceContext[] = [];

      const updateAssistant = (updater: (message: Message) => Message) => {
        setMessages((prev) => {
          const next = [...prev];
          for (let i = next.length - 1; i >= 0; i -= 1) {
            if (next[i].role === 'assistant') {
              next[i] = updater(next[i]);
              break;
            }
          }
          return next;
        });
      };

      const handleEvent = (event: any) => {
        if (event.type === 'status') {
          updateAssistant((msg) => ({ ...msg, status: event.message || msg.status }));
          return;
        }
        if (event.type === 'clarification') {
          updateAssistant((msg) => ({
            ...msg,
            status: '',
            clarification: event.clarification,
          }));
          return;
        }
        if (event.type === 'retrieved') {
          retrievedAssets = event.assets || [];
          retrievedSources = event.raw_contexts || [];
          updateAssistant((msg) => ({
            ...msg,
            status: `已召回 ${event.contexts_count || 0} 条资料、${event.assets_count || 0} 个图片资产，正在生成回答...`,
            images: event.images || [],
            sources: retrievedSources,
            assets: retrievedAssets,
          }));
          return;
        }
        if (event.type === 'chunk') {
          hasContent = true;
          streamedAnswer += event.content || '';
          updateAssistant((msg) => ({
            ...msg,
            content: `${msg.content || ''}${event.content || ''}`,
            status: '',
          }));
          return;
        }
        if (event.type === 'done') {
          updateAssistant((msg) => ({
            ...msg,
            streaming: false,
            status: '',
            followups: buildFollowupQuestions(userMessage.content, msg.content || '', msg.assets, msg.sources),
            followupLoading: true,
          }));
          return;
        }
        if (event.type === 'error') {
          throw new Error(event.error || '检索知识库出错');
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() || '';
        for (const frame of frames) {
          const dataLine = frame.split('\n').find((line) => line.startsWith('data:'));
          if (!dataLine) continue;
          const raw = dataLine.replace(/^data:\s*/, '');
          if (!raw) continue;
          handleEvent(JSON.parse(raw));
        }
      }

      if (!hasContent) {
        updateAssistant((msg) => ({
          ...msg,
          streaming: false,
          status: '',
          content: msg.content || '未生成有效回答，请换一个问题重试。',
        }));
      } else {
        try {
          const followupRes = await fetch('/api/knowledge/followups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              question: userMessage.content,
              answer: streamedAnswer,
              assets: retrievedAssets,
              sources: retrievedSources,
            }),
          });
          if (followupRes.ok) {
            const followupData = await followupRes.json();
            const modelFollowups = Array.isArray(followupData.followups)
              ? followupData.followups.filter((item: unknown): item is string => typeof item === 'string' && Boolean(item.trim()))
              : [];
            updateAssistant((msg) => ({
              ...msg,
              followups: modelFollowups.length ? uniqueQuestions(modelFollowups) : msg.followups,
              followupLoading: false,
            }));
          } else {
            updateAssistant((msg) => ({ ...msg, followupLoading: false }));
          }
        } catch {
          updateAssistant((msg) => ({ ...msg, followupLoading: false }));
        }
      }
    } catch (err: any) {
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i -= 1) {
          if (next[i].role === 'assistant') {
            next[i] = {
              ...next[i],
              streaming: false,
              status: '',
              followupLoading: false,
              content: next[i].content || '检索知识库出错，请稍后重试。',
            };
            break;
          }
        }
        return next;
      });
      message.error(err.message || '检索知识库出错');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Drawer
      title="企业知识库助手"
      placement="right"
      width={720}
      onClose={onClose}
      open={visible}
      bodyStyle={{ display: 'flex', flexDirection: 'column', padding: 0 }}
    >
      <div className="border-b border-slate-100 bg-white px-4 py-3">
        <Space wrap size={[8, 8]}>
          <Select
            value={scopeKey}
            style={{ width: 260 }}
            onChange={setScopeKey}
            options={[
              { label: '自动判断资料范围', value: 'auto' },
              ...scopes.map((scope, index) => ({
                label: scopeLabel(scope),
                value: String(index),
              })),
            ]}
          />
          <Select
            value={scenario}
            style={{ width: 132 }}
            onChange={setScenario}
            options={scenarioOptions.map((item) => ({ label: item.label, value: item.value }))}
          />
          {selectedScope && (
            <Tag color="blue" className="m-0 max-w-[280px] truncate py-1">
              {scopeLabel(selectedScope)}
            </Tag>
          )}
        </Space>
      </div>
      <div className="flex-1 overflow-y-auto bg-slate-50 p-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-400">
            <SearchOutlined style={{ fontSize: 48, marginBottom: 16 }} />
            <Text type="secondary">试着问我关于电网招标文件、技术规范书、标准话术和投标章节的问题</Text>
            <Text type="secondary" className="mt-2 text-xs">可检索企业资料、产品图片、资质样张和电网行业知识</Text>
            <div className="mt-6 w-full space-y-3">
              {guideQuestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => handleSearch(question)}
                  className="w-full rounded-xl border border-blue-100 bg-white px-4 py-3 text-left text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <List
            dataSource={messages}
            renderItem={(msg, index) => (
              <div key={index} className={`mb-6 flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`${msg.role === 'assistant' ? 'max-w-[94%]' : 'max-w-[85%]'} rounded-2xl p-4 shadow-sm ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-tr-sm'
                      : 'bg-white border border-slate-100 rounded-tl-sm'
                  }`}
                >
                  <div className={`max-w-none text-[15px] leading-7 ${msg.role === 'user' ? 'text-white' : 'text-slate-700'}`}>
                    {msg.status && (
                      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-500">
                        <BrandMark size={24} className="brand-loading-logo brand-loading-logo-sm" />
                        <span>{msg.status}</span>
                      </div>
                    )}
                    {msg.content ? (
                      <ReactMarkdown
                        components={{
                          h2: ({ children }) => (
                            <h2 className="mb-2 mt-4 border-l-4 border-blue-500 pl-3 text-base font-bold text-slate-900 first:mt-0">
                              {children}
                            </h2>
                          ),
                          h3: ({ children }) => (
                            <h3 className="mb-2 mt-3 text-sm font-bold text-slate-800">{children}</h3>
                          ),
                          p: ({ children }) => (
                            <p className="my-2 whitespace-pre-wrap text-[15px] leading-7">{children}</p>
                          ),
                          ul: ({ children }) => (
                            <ul className="my-2 space-y-1 pl-5">{children}</ul>
                          ),
                          ol: ({ children }) => (
                            <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>
                          ),
                          li: ({ children }) => (
                            <li className="list-disc pl-1 text-[15px] leading-7">{children}</li>
                          ),
                          strong: ({ children }) => (
                            <strong className={msg.role === 'user' ? 'font-bold text-white' : 'font-bold text-slate-950'}>
                              {children}
                            </strong>
                          ),
                          blockquote: ({ children }) => (
                            <blockquote className="my-3 rounded-lg border-l-4 border-slate-300 bg-slate-50 px-3 py-2 text-slate-600">
                              {children}
                            </blockquote>
                          ),
                          a: ({ children, href }) => (
                            <a href={href} target="_blank" rel="noreferrer" className="font-semibold text-blue-600 hover:text-blue-700">
                              {children}
                            </a>
                          ),
                          img: ({ alt, src }) => (
                            <span className="my-3 block">
                              <Image
                                src={src || ''}
                                alt={alt || '知识库图片'}
                                className="max-h-64 rounded-xl border border-slate-200 object-contain"
                                preview={{ src }}
                              />
                              {alt && (
                                <span className="mt-1 block text-center text-xs font-semibold text-slate-400">
                                  {alt}
                                </span>
                              )}
                            </span>
                          ),
                        }}
                      >
                        {msg.role === 'assistant' ? withInlineAssetImages(msg.content, msg.assets) : msg.content}
                      </ReactMarkdown>
                    ) : null}
                    {msg.streaming && msg.content && <span className="ml-1 inline-block h-4 w-1 animate-pulse rounded bg-blue-500 align-middle" />}
                  </div>

                  {msg.role === 'assistant' && msg.clarification?.scopes?.length ? (
                    <div className="mt-4 rounded-xl border border-amber-100 bg-amber-50 p-3">
                      <div className="mb-2 text-xs font-bold text-amber-800">请选择要查询的资料范围</div>
                      <div className="grid gap-2">
                        {msg.clarification.scopes.slice(0, 6).map((scope) => (
                          <button
                            key={`${scope.ingestion_batch_id}-${scope.province}-${scope.package_code}-${scope.material_category}`}
                            type="button"
                            disabled={loading}
                            onClick={() => {
                              const matchedIndex = scopes.findIndex((item) =>
                                item.ingestion_batch_id === scope.ingestion_batch_id
                                && item.province === scope.province
                                && item.package_code === scope.package_code
                                && item.material_category === scope.material_category
                              );
                              if (matchedIndex >= 0) setScopeKey(String(matchedIndex));
                              handleSearch(msg.sourceQuery || '', scope);
                            }}
                            className="rounded-lg border border-amber-200 bg-white px-3 py-2 text-left text-xs font-bold text-amber-900 hover:border-amber-400 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {scopeLabel(scope)}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {msg.role === 'assistant' && !msg.streaming && msg.followups && msg.followups.length > 0 && (
                    <div className="mt-4 border-t border-slate-100 pt-4">
                      <div className="mb-2 flex items-center gap-2 text-xs font-bold text-slate-500">
                        <span>你可以继续问</span>
                        {msg.followupLoading && (
                          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] text-blue-600">
                            AI 正在优化
                          </span>
                        )}
                      </div>
                      <div className="flex flex-col gap-2">
                        {msg.followups.map((question) => (
                          <button
                            key={question}
                            type="button"
                            disabled={loading}
                            onClick={() => handleSearch(question)}
                            className="rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-left text-xs font-bold text-blue-700 transition hover:border-blue-300 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {question}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {msg.role === 'assistant' && !msg.streaming && msg.sources && msg.sources.length > 0 && (
                    <div className="mt-4 border-t border-slate-100 pt-4">
                      <div className="mb-2 text-xs font-bold text-slate-500">参考资料来源</div>
                      <div className="space-y-2">
                        {msg.sources.slice(0, 5).map((source, sourceIndex) => {
                          const meta = source.metadata || {};
                          return (
                            <div key={`${sourceTitle(source)}-${sourceIndex}`} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="line-clamp-2 text-sm font-bold leading-5 text-slate-800">
                                    资料{sourceIndex + 1}：{sourceTitle(source)}
                                  </div>
                                  <div className="mt-1 text-xs font-semibold text-slate-400">
                                    {sourceDescription(source)}
                                  </div>
                                  <div className="mt-2 flex flex-wrap gap-1">
                                    {meta.doc_role && <Tag className="m-0" color="geekblue">{docRoleLabel[meta.doc_role] || meta.doc_role}</Tag>}
                                    {meta.province && <Tag className="m-0" color="cyan">{meta.province}</Tag>}
                                    {meta.package_code && <Tag className="m-0" color="purple">{meta.package_code}</Tag>}
                                    {meta.material_category && <Tag className="m-0" color="green">{meta.material_category}</Tag>}
                                  </div>
                                </div>
                                {typeof source.similarity === 'number' && (
                                  <span className="shrink-0 rounded-full bg-blue-50 px-2 py-1 text-xs font-bold text-blue-600">
                                    {(source.similarity * 100).toFixed(0)}%
                                  </span>
                                )}
                              </div>
                              {previewText(source.content) && (
                                <div className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">
                                  {previewText(source.content)}
                                </div>
                              )}
                              {meta.source_url && (
                                <a
                                  href={meta.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="mt-2 inline-block text-xs font-bold text-blue-600 hover:text-blue-700"
                                >
                                  查看原始来源
                                </a>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          />
        )}
      </div>
      <div className="p-4 bg-white border-t border-slate-100">
        <Input
          size="large"
          placeholder="输入您想查询的知识..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onPressEnter={() => handleSearch()}
          suffix={
            <Button
              type="primary"
              shape="circle"
              icon={<SendOutlined />}
              onClick={() => handleSearch()}
              loading={loading}
              className="flex items-center justify-center"
            />
          }
          className="rounded-full px-4"
        />
      </div>
    </Drawer>
  );
}
