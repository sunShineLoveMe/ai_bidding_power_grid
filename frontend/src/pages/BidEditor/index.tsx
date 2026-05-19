import { Fragment, useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { Alert, Button, Drawer, Dropdown, Empty, Form, Input, InputNumber, List, Modal, Progress, Radio, Segmented, Space, Tag, Tooltip, message } from 'antd';
import type { MenuProps } from 'antd';
import {
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
  FileText,
  MoreVertical,
  Plus,
  Search,
  Sparkles,
  Square,
  ArrowUp,
  ArrowDown,
  Eye,
  Trash2,
  SlidersHorizontal,
  RotateCcw,
  Clock3,
  Gauge,
  Save,
  RefreshCw,
  AlertTriangle,
  ShieldAlert,
} from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  cancelSectionGenerationTask,
  createSectionGenerationTask,
  deleteBidSection,
  generateBidDocxDownload,
  getBidExportTask,
  generateComplianceSupplement,
  getComplianceCheck,
  getInterpretation,
  getLatestInterpretation,
  getLatestSectionGenerationTask,
  reorderBidSections,
  resetBidSectionsGeneration,
  runSemanticComplianceCheck,
  saveBidSection,
  saveBidLengthSettings,
  updateSectionGenerationTaskItem,
} from '../../api/bidProject';
import type { SectionGenerationTask } from '../../api/bidProject';
import type { BidExportTask } from '../../api/bidProject';
import { BrandMark } from '../../components/common/BrandMark';
import { TiptapBidEditor } from '../../components/editor/TiptapBidEditor';
import type { BidLengthFeasibility, BidLengthSettings, BidOutline, BidOutlineChapter, BidSection, ChapterWritingPlan, ComplianceReport, ComplianceRow, InterpretationResponse, SemanticComplianceReport, SemanticComplianceReview } from '../../types/interpretation';

type EditorMode = '正文模式' | '目录模式';
type VolumeType = 'all' | 'technical' | 'business';
type InternalVolumeType = 'technical' | 'business' | 'qualification' | 'price' | 'attachment' | 'other';

type ChapterDraft = BidOutlineChapter & {
  id: string;
  content: string;
  expanded: boolean;
};

type AddChapterOptions = {
  parent?: ChapterDraft | null;
};

type StreamingChildPlaceholder = {
  id: string;
  parentOrder: string;
  title: string;
};

type BatchTaskStatus = 'queued' | 'running' | 'done' | 'failed' | 'stopped';

type BatchTask = {
  status: BatchTaskStatus;
  percent: number;
  chars: number;
  targetWords: number;
  message?: string;
};

type PersistedBatchTask = {
  id: string;
  status: SectionGenerationTask['status'];
};

const BATCH_SECTION_CONCURRENCY = 3;
const DEFAULT_LENGTH_SETTINGS: BidLengthSettings = {
  mode: 'pages',
  technicalPages: 80,
  businessPages: 40,
  technicalWords: 56000,
  businessWords: 22000,
  allowAutoExpand: false,
};
const WORDS_PER_PAGE = {
  technical: 700,
  business: 550,
};

const volumeOptions: Array<{ value: VolumeType; label: string; shortLabel: string }> = [
  { value: 'all', label: '全部', shortLabel: '全部' },
  { value: 'technical', label: '技术标', shortLabel: '技术' },
  { value: 'business', label: '商务标', shortLabel: '商务' },
];

const internalVolumeOptions: Array<{ value: InternalVolumeType; label: string; keywords: RegExp }> = [
  { value: 'technical', label: '技术标', keywords: /技术|施工组织|实施方案|施工方案|质量|安全|环保|进度|资源配置|发包人要求|承包人建议|设备|工艺|调试/ },
  { value: 'business', label: '商务响应', keywords: /商务|合同|付款|履约|服务|税费|廉政|保密|偏离|承诺|投标函|授权委托|保证金/ },
  { value: 'qualification', label: '资格文件', keywords: /资格|资质|证书|营业执照|安全生产许可|人员|项目经理|技术负责人|业绩|信誉|社保|建造师/ },
  { value: 'price', label: '报价文件', keywords: /报价|清单|价格|单价|工程量|投标总价|分项报价/ },
  { value: 'attachment', label: '附件材料', keywords: /附件|图纸|扫描件|证明材料|附录|图片|图册/ },
  { value: 'other', label: '其他', keywords: /^$/ },
];

function asBidOutline(meta: Record<string, unknown> | undefined | null): BidOutline | null {
  return (meta?.bid_outline || null) as BidOutline | null;
}

function asBidLengthSettings(meta: Record<string, unknown> | undefined | null): BidLengthSettings {
  const raw = (meta?.length_settings || {}) as Partial<BidLengthSettings>;
  const mode = raw.mode === 'words' ? 'words' : 'pages';
  const technicalPages = Number(raw.technicalPages || DEFAULT_LENGTH_SETTINGS.technicalPages);
  const businessPages = Number(raw.businessPages || DEFAULT_LENGTH_SETTINGS.businessPages);
  const technicalWords = Number(raw.technicalWords || technicalPages * WORDS_PER_PAGE.technical);
  const businessWords = Number(raw.businessWords || businessPages * WORDS_PER_PAGE.business);
  return {
    mode,
    technicalPages,
    businessPages,
    technicalWords,
    businessWords,
    allowAutoExpand: Boolean(raw.allowAutoExpand),
  };
}

function asBidLengthFeasibility(meta: Record<string, unknown> | undefined | null): BidLengthFeasibility | null {
  return (meta?.length_feasibility || null) as BidLengthFeasibility | null;
}

function normalizeLengthFormValues(values: Partial<BidLengthSettings>): BidLengthSettings {
  const mode = values.mode === 'words' ? 'words' : 'pages';
  const technicalPages = Math.max(1, Number(values.technicalPages || DEFAULT_LENGTH_SETTINGS.technicalPages));
  const businessPages = Math.max(1, Number(values.businessPages || DEFAULT_LENGTH_SETTINGS.businessPages));
  let technicalWords = Math.max(1, Number(values.technicalWords || DEFAULT_LENGTH_SETTINGS.technicalWords));
  let businessWords = Math.max(1, Number(values.businessWords || DEFAULT_LENGTH_SETTINGS.businessWords));
  let nextTechnicalPages = technicalPages;
  let nextBusinessPages = businessPages;
  if (mode === 'pages') {
    technicalWords = technicalPages * WORDS_PER_PAGE.technical;
    businessWords = businessPages * WORDS_PER_PAGE.business;
  } else {
    nextTechnicalPages = Math.max(1, Math.round(technicalWords / WORDS_PER_PAGE.technical));
    nextBusinessPages = Math.max(1, Math.round(businessWords / WORDS_PER_PAGE.business));
  }
  return {
    mode,
    technicalPages: nextTechnicalPages,
    businessPages: nextBusinessPages,
    technicalWords,
    businessWords,
    allowAutoExpand: Boolean(values.allowAutoExpand),
  };
}

function localLengthWarnings(settings: BidLengthSettings): string[] {
  const warnings: string[] = [];
  if (settings.technicalPages > 180) {
    warnings.push(`技术标目标 ${settings.technicalPages} 页偏高，建议补充专项施工方案、设备参数、进度资源、质量安全和图纸材料后再扩写。`);
  }
  if (settings.businessPages > 120) {
    warnings.push(`商务标目标 ${settings.businessPages} 页偏高，资格、报价和附件类章节将以资料完整性和人工复核为主，不建议按篇幅灌水。`);
  }
  if (settings.technicalPages + settings.businessPages >= 300) {
    warnings.push('总目标页数达到 300 页以上，建议拆分多轮生成和人工复核，避免重复、泛化或证据不足。');
  }
  return warnings;
}

function makeChapterId(chapter: BidOutlineChapter, index: number): string {
  return `${chapter.order_index || chapter.order || index + 1}-${chapter.title || 'chapter'}`;
}

function initialContent(chapter: BidOutlineChapter): string {
  const responsePoints = chapter.response_points?.map(item => `（${item}）`).join('\n') || '（待补充响应要点）';
  const materials = chapter.required_materials?.join('、') || '需人工补充企业资料、资信文件和证明材料';
  const risks = chapter.mapped_risks?.join('；') || '暂无明确风险，仍需结合招标文件复核。';

  return [
    `## ${chapter.title || '未命名章节'}`,
    '',
    chapter.purpose || '本章用于响应招标文件相关要求，待进一步生成正文。',
    '',
    '### 编写要点',
    responsePoints,
    '',
    '### 需准备资料',
    materials,
    '',
    '### 风险与复核',
    risks,
  ].join('\n');
}

function normalizeChapterHierarchy(items: ChapterDraft[]): ChapterDraft[] {
  const childrenByParent = new Map<string, ChapterDraft[]>();
  const roots: ChapterDraft[] = [];
  const existingIds = new Set(items.map(item => item.id));

  items.forEach(item => {
    if (item.parent_id && existingIds.has(item.parent_id)) {
      const siblings = childrenByParent.get(item.parent_id) || [];
      siblings.push(item);
      childrenByParent.set(item.parent_id, siblings);
      return;
    }
    roots.push(item.parent_id ? { ...item, parent_id: null } : item);
  });

  const ordered: ChapterDraft[] = [];
  const visit = (nodes: ChapterDraft[], prefix = '', depth = 1): void => {
    nodes.forEach((node, index) => {
      const nextOrder = prefix ? `${prefix}.${index + 1}` : `${index + 1}`;
      ordered.push({
        ...node,
        order: nextOrder,
        level: depth,
      });
      const children = [...(childrenByParent.get(node.id) || [])];
      if (children.length) {
        visit(children, nextOrder, Math.min(depth + 1, 4));
      }
    });
  };

  visit(roots);
  return ordered.map((item, index) => ({ ...item, order_index: index + 1 }));
}

function flattenChapters(outline: BidOutline | null): ChapterDraft[] {
  const outlineChapters = outline?.chapters?.length
    ? outline.chapters
    : (outline?.volumes || []).flatMap(volume => (volume.chapters || []).map(chapter => ({
      ...chapter,
      metadata: {
        ...(chapter.metadata || {}),
        volume_type: chapter.metadata?.volume_type || volume.type,
        volume_name: chapter.metadata?.volume_name || volume.name,
      },
    })));
  return normalizeChapterHierarchy((outlineChapters || []).map((chapter, index) => ({
    ...chapter,
    id: makeChapterId(chapter, index),
    content: initialContent(chapter),
    expanded: true,
  })));
}

function sectionsToDrafts(sections?: BidSection[]): ChapterDraft[] {
  return normalizeChapterHierarchy((sections || []).map(section => ({
    ...section,
    order: section.order_index,
    level: section.level || 1,
    content: section.content || initialContent(section),
    expanded: true,
  })));
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}

function numericOrderIndex(value: string | number | undefined, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  return fallback;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function chapterDisplayTitle(chapter: Pick<ChapterDraft, 'order' | 'title'>): string {
  const title = (chapter.title || '未命名章节').trim();
  if (!chapter.order) {
    return title;
  }
  const order = String(chapter.order).trim();
  const duplicateOrder = new RegExp(`^${escapeRegExp(order)}\\.?\\s*`);
  const cleanTitle = title.replace(duplicateOrder, '').trim() || title;
  const orderPrefix = order.includes('.') ? `${order} ` : `${order}. `;
  return `${orderPrefix}${cleanTitle}`;
}

function inferVolumeType(chapter: Pick<ChapterDraft, 'title' | 'purpose' | 'required_materials' | 'response_points' | 'metadata'>): InternalVolumeType {
  const metadataVolume = String(chapter.metadata?.volume_type || '').trim() as InternalVolumeType;
  if (internalVolumeOptions.some(item => item.value === metadataVolume)) {
    return metadataVolume;
  }
  const combined = [
    chapter.title,
    chapter.purpose,
    ...(chapter.required_materials || []),
    ...(chapter.response_points || []),
  ].filter(Boolean).join(' ');
  const matched = internalVolumeOptions.find(item => item.value !== 'other' && item.keywords.test(combined));
  return matched?.value || 'other';
}

function volumeLabel(volumeType: VolumeType): string {
  return volumeOptions.find(item => item.value === volumeType)?.label || '其他';
}

function internalVolumeLabel(volumeType: InternalVolumeType): string {
  return internalVolumeOptions.find(item => item.value === volumeType)?.label || '其他';
}

function deliveryVolumeType(chapter: Pick<ChapterDraft, 'title' | 'purpose' | 'required_materials' | 'response_points' | 'metadata'>): VolumeType {
  return inferVolumeType(chapter) === 'technical' ? 'technical' : 'business';
}

function matchesActiveVolume(chapter: ChapterDraft, activeVolume: VolumeType): boolean {
  if (activeVolume === 'all') {
    return true;
  }
  return deliveryVolumeType(chapter) === activeVolume;
}

function safeParentIdForSave(parentId: string | null | undefined, chapters: ChapterDraft[]): string | null {
  if (!parentId || !isUuid(parentId)) {
    return null;
  }
  return chapters.some(item => item.id === parentId) ? parentId : null;
}

export function BidEditorPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<InterpretationResponse | null>(null);
  const [outlineMeta, setOutlineMeta] = useState<BidOutline | null>(null);
  const [chapters, setChapters] = useState<ChapterDraft[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');
  const [mode, setMode] = useState<EditorMode>('正文模式');
  const [activeVolume, setActiveVolume] = useState<VolumeType>('all');
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [sectionStreaming, setSectionStreaming] = useState(false);
  const [streamText, setStreamText] = useState('');
  const [streamingChildPlaceholders, setStreamingChildPlaceholders] = useState<StreamingChildPlaceholder[]>([]);
  const [downloadUrl, setDownloadUrl] = useState('');
  const [downloadGenerating, setDownloadGenerating] = useState<'full' | 'section' | null>(null);
  const [exportTask, setExportTask] = useState<BidExportTask | null>(null);
  const [complianceReport, setComplianceReport] = useState<ComplianceReport | null>(null);
  const [complianceRefreshing, setComplianceRefreshing] = useState(false);
  const [complianceLastCheckedAt, setComplianceLastCheckedAt] = useState<Date | null>(null);
  const [complianceError, setComplianceError] = useState('');
  const [complianceDrawerOpen, setComplianceDrawerOpen] = useState(false);
  const [semanticReport, setSemanticReport] = useState<SemanticComplianceReport | null>(null);
  const [semanticRefreshing, setSemanticRefreshing] = useState(false);
  const [semanticDrawerOpen, setSemanticDrawerOpen] = useState(false);
  const [qualityCollapsed, setQualityCollapsed] = useState(false);
  const [supplementingRowId, setSupplementingRowId] = useState('');
  const [contentDirty, setContentDirty] = useState(false);
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [batchTasks, setBatchTasks] = useState<Record<string, BatchTask>>({});
  const [withImages, setWithImages] = useState(false);
  const [resetModalOpen, setResetModalOpen] = useState(false);
  const [resetClearContent, setResetClearContent] = useState(false);
  const [resettingGeneration, setResettingGeneration] = useState(false);
  const [persistedBatchTask, setPersistedBatchTask] = useState<PersistedBatchTask | null>(null);
  const [lengthSettingsOpen, setLengthSettingsOpen] = useState(false);
  const [lengthSettingsSaving, setLengthSettingsSaving] = useState(false);
  const [lengthFeasibility, setLengthFeasibility] = useState<BidLengthFeasibility | null>(null);
  const [lengthForm] = Form.useForm<BidLengthSettings>();
  const streamStartedRef = useRef(false);
  const batchCancelRequestedRef = useRef(false);
  const batchAbortControllersRef = useRef<Map<string, AbortController>>(new Map());
  const persistedBatchTaskIdRef = useRef('');
  const batchTaskSyncAtRef = useRef<Map<string, number>>(new Map());

  function applyPersistedBatchTask(task: SectionGenerationTask | null, sourceChapters: ChapterDraft[] = chapters): void {
    if (!task?.id || !Array.isArray(task.items) || !task.items.length) {
      setPersistedBatchTask(null);
      persistedBatchTaskIdRef.current = '';
      return;
    }
    const generatedIds = new Set(sourceChapters.filter(isChapterGenerated).map(chapter => chapter.id));
    const activeItems = task.items.filter(item => {
      if (generatedIds.has(item.section_id) && (item.status === 'queued' || item.status === 'running')) {
        return false;
      }
      return item.status === 'queued' || item.status === 'running' || item.status === 'failed' || item.status === 'stopped';
    });
    const nextTasks = Object.fromEntries(activeItems.map(item => [item.section_id, {
      status: generatedIds.has(item.section_id) && item.status !== 'failed' && item.status !== 'stopped' ? 'done' : item.status,
      percent: generatedIds.has(item.section_id) ? 100 : item.percent || 0,
      chars: item.chars || 0,
      targetWords: item.target_words || 800,
      message: generatedIds.has(item.section_id) ? '已完成' : item.message || item.error || batchStatusLabel(item.status),
    } satisfies BatchTask]));
    setPersistedBatchTask({ id: task.id, status: task.status });
    persistedBatchTaskIdRef.current = task.id;
    setBatchTasks(nextTasks);
  }

  async function refreshLatestBatchTask(projectId: string, sourceChapters?: ChapterDraft[]): Promise<void> {
    try {
      const task = await getLatestSectionGenerationTask(projectId);
      applyPersistedBatchTask(task, sourceChapters || chapters);
    } catch (error) {
      console.warn('恢复批量章节生成任务失败', error);
    }
  }

  function complianceVolumeParam(volume: VolumeType = activeVolume): string | undefined {
    return volume === 'all' ? undefined : volume;
  }

  async function refreshComplianceReport(projectId: string, options?: { silent?: boolean; volumeType?: VolumeType }): Promise<void> {
    if (!options?.silent) {
      setComplianceRefreshing(true);
    }
    setComplianceError('');
    try {
      const report = await getComplianceCheck(projectId, {
        volumeType: complianceVolumeParam(options?.volumeType),
      });
      setComplianceReport(report);
      setComplianceLastCheckedAt(new Date());
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      setComplianceError(reason || '条款响应检查失败');
      if (!options?.silent) {
        message.warning(`条款响应检查失败：${reason}`);
      }
    } finally {
      if (!options?.silent) {
        setComplianceRefreshing(false);
      }
    }
  }

  async function runSemanticReview(projectId: string): Promise<void> {
    setSemanticRefreshing(true);
    try {
      const report = await runSemanticComplianceCheck(projectId, {
        volumeType: complianceVolumeParam(activeVolume),
        limit: 12,
        useLlm: true,
      });
      setSemanticReport(report);
      setSemanticDrawerOpen(true);
      message.success(`语义复核完成：已复核 ${report.summary.total} 项`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setSemanticRefreshing(false);
    }
  }

  function openLengthSettings(): void {
    const settings = asBidLengthSettings(data?.analysis?.project_meta);
    lengthForm.setFieldsValue(settings);
    setLengthFeasibility(asBidLengthFeasibility(data?.analysis?.project_meta));
    setLengthSettingsOpen(true);
  }

  async function saveLengthSettings(): Promise<void> {
    if (!data?.project?.id) {
      message.warning('当前项目不存在，无法保存全文设置。');
      return;
    }
    try {
      const values = await lengthForm.validateFields();
      const settings = normalizeLengthFormValues(values);
      setLengthSettingsSaving(true);
      const result = await saveBidLengthSettings(data.project.id, settings);
      const drafts = sectionsToDrafts(result.sections || []);
      setChapters(drafts);
      setData(current => current ? {
        ...current,
        sections: result.sections || current.sections,
        analysis: current.analysis ? {
          ...current.analysis,
          project_meta: {
            ...(current.analysis.project_meta || {}),
            length_settings: result.settings,
            length_feasibility: result.feasibility,
          },
        } : current.analysis,
      } : current);
      setLengthFeasibility(result.feasibility);
      setSelectedId(current => current || drafts[0]?.id || '');
      setLengthSettingsOpen(false);
      const allocatedWords = (result.allocations || []).reduce((sum, item) => sum + (Number(item.targetWords) || 0), 0);
      const targetWords = settings.technicalWords + settings.businessWords;
      message.success(`全文篇幅设置已保存，章节计划 ${allocatedWords.toLocaleString()} / 用户目标 ${targetWords.toLocaleString()} 字`);
    } catch (error) {
      if (error && typeof error === 'object' && 'errorFields' in error) {
        return;
      }
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLengthSettingsSaving(false);
    }
  }

  async function load(): Promise<void> {
    setLoading(true);
    setDownloadUrl('');
    try {
      const projectId = searchParams.get('projectId');
      const result = projectId ? await getInterpretation(projectId) : await getLatestInterpretation();
      setData(result);
      setLengthFeasibility(asBidLengthFeasibility(result.analysis?.project_meta));
      setContentDirty(false);
      let loadedDrafts: ChapterDraft[] = [];
      if (searchParams.get('autoGenerate') === 'outline' && result.project?.id) {
        startOutlineStream(result.project.id);
      } else {
        const outline = asBidOutline(result.analysis?.project_meta);
        setOutlineMeta(outline);
        const sectionDrafts = sectionsToDrafts(result.sections);
        const drafts = sectionDrafts.length ? sectionDrafts : flattenChapters(outline);
        loadedDrafts = drafts;
        setChapters(drafts);
        setSelectedId(current => current || drafts[0]?.id || '');
      }
      if (result.project?.id) {
        void refreshComplianceReport(result.project.id, { silent: true });
        void refreshLatestBatchTask(result.project.id, loadedDrafts);
      }
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      message.error(reason);
    } finally {
      setLoading(false);
    }
  }

  async function reloadProject(projectId: string): Promise<void> {
    const result = await getInterpretation(projectId);
    const outline = asBidOutline(result.analysis?.project_meta);
    const sectionDrafts = sectionsToDrafts(result.sections);
    const drafts = sectionDrafts.length ? sectionDrafts : flattenChapters(outline);
    setData(result);
    setLengthFeasibility(asBidLengthFeasibility(result.analysis?.project_meta));
    setOutlineMeta(outline);
    setChapters(drafts);
    setSelectedId(current => current || drafts[0]?.id || '');
    setContentDirty(false);
    void refreshComplianceReport(projectId, { silent: true });
    void refreshLatestBatchTask(projectId, drafts);
  }

  useEffect(() => {
    void load();
    // searchParams is stable enough for this route-level load; it changes only when projectId changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // 处理编辑器内容变化
  const handleEditorChange = useCallback((markdown: string) => {
    if (selectedId) {
      setChapters(items => items.map(item =>
        item.id === selectedId ? { ...item, content: markdown } : item
      ));
      setContentDirty(true);
    }
  }, [selectedId]);

  function startOutlineStream(projectId: string): void {
    if (streamStartedRef.current) {
      return;
    }
    streamStartedRef.current = true;
    setStreaming(true);
    setStreamText('AI 正在分析招标解读结果，准备生成标书章节大纲...');
    setChapters([]);
    setSelectedId('');
    setStreamingChildPlaceholders([]);

    const source = new EventSource(`/api/bidding/interpretations/${projectId}/bid-outline/stream`);
    source.addEventListener('start', event => {
      const payload = JSON.parse((event as MessageEvent).data) as { message?: string };
      setStreamText(payload.message || 'AI 已开始生成章节大纲。');
    });
    source.addEventListener('meta', event => {
      const payload = JSON.parse((event as MessageEvent).data) as { outline: BidOutline; total: number; rootTotal?: number; phase?: string };
      setOutlineMeta({ ...payload.outline, chapters: [] });
      setStreamText(payload.phase === 'quick'
        ? `已生成快速目录骨架，预计 ${payload.total} 个章节，正在逐步展开。`
        : `AI 已开始生成章节大纲，预计 ${payload.total} 个章节。`);
    });
    source.addEventListener('refined', event => {
      const payload = JSON.parse((event as MessageEvent).data) as { outline: BidOutline; total: number; rootTotal?: number };
      setOutlineMeta({ ...payload.outline, chapters: [] });
      setChapters([]);
      setSelectedId('');
      setStreamingChildPlaceholders([]);
      setStreamText(`AI 复核完成，正在刷新最终章节大纲，共 ${payload.total} 个章节。`);
    });
    source.addEventListener('stage', event => {
      const payload = JSON.parse((event as MessageEvent).data) as { message?: string; stage?: string; chapter?: { rootOrder?: string } };
      if (payload.message) {
        setStreamText(payload.message);
      }
      if (payload.stage === 'children' && payload.chapter?.rootOrder) {
        setStreamingChildPlaceholders(items => items.filter(item => item.parentOrder !== payload.chapter?.rootOrder));
      }
    });
    source.addEventListener('chapter', event => {
      const payload = JSON.parse((event as MessageEvent).data) as { chapter: BidOutlineChapter; index: number; total: number; phase?: string };
      const chapterDraft: ChapterDraft = {
        ...payload.chapter,
        id: makeChapterId(payload.chapter, payload.index - 1),
        content: initialContent(payload.chapter),
        expanded: true,
      };
      setChapters(items => {
        if (items.some(item => item.id === chapterDraft.id)) {
          return items;
        }
        return [...items, chapterDraft];
      });
      setSelectedId(current => current || chapterDraft.id);
      setStreamText(`${payload.phase === 'refined' ? '正在刷新最终章节' : '正在生成章节'} ${payload.index} / ${payload.total}：${payload.chapter.title || '未命名章节'}`);
      if ((payload.chapter.level || 1) === 1) {
        const parentOrder = String(payload.chapter.order || '');
        if (parentOrder) {
          setStreamingChildPlaceholders(items => [
            ...items.filter(item => item.parentOrder !== parentOrder),
            {
              id: `streaming-child-${parentOrder}`,
              parentOrder,
              title: `正在补充「${payload.chapter.title || parentOrder}」下的子章节...`,
            },
          ]);
        }
      } else {
        const parentOrder = String(payload.chapter.order || '').split('.', 1)[0];
        if (parentOrder) {
          setStreamingChildPlaceholders(items => items.filter(item => item.parentOrder !== parentOrder));
        }
      }
    });
    source.addEventListener('done', event => {
      const payload = JSON.parse((event as MessageEvent).data) as { outline: BidOutline };
      setOutlineMeta(payload.outline);
      setData(current => current ? { ...current, sections: [] } : current);
      setStreamText('标书章节大纲生成完成，已进入可编辑状态。');
      setStreaming(false);
      setStreamingChildPlaceholders([]);
      source.close();
      window.history.replaceState(null, '', `/bid-editor?projectId=${projectId}`);
      void reloadProject(projectId);
    });
    source.addEventListener('error', event => {
      const raw = (event as MessageEvent).data;
      if (raw) {
        try {
          const payload = JSON.parse(raw) as { error?: string };
          message.error(payload.error || '章节大纲流式生成失败');
        } catch {
          message.error('章节大纲流式生成失败');
        }
      }
      setStreaming(false);
      setStreamingChildPlaceholders([]);
      source.close();
    });
  }

  const savedOutline = asBidOutline(data?.analysis?.project_meta);
  const outline = outlineMeta || savedOutline;
  const lengthSettings = useMemo(() => asBidLengthSettings(data?.analysis?.project_meta), [data?.analysis?.project_meta]);
  const volumeCounts = useMemo(() => {
    const counts = Object.fromEntries(volumeOptions.map(item => [item.value, 0])) as Record<VolumeType, number>;
    chapters.forEach(chapter => {
      counts[deliveryVolumeType(chapter)] += 1;
      counts.all += 1;
    });
    return counts;
  }, [chapters]);
  const filteredChapters = useMemo(() => {
    const term = keyword.trim();
    const volumeFiltered = activeVolume === 'all'
      ? chapters
      : chapters.filter(chapter => matchesActiveVolume(chapter, activeVolume));
    if (!term) {
      return volumeFiltered;
    }
    const matchedIds = new Set(volumeFiltered.filter(chapter => (chapter.title || '').includes(term)).map(chapter => chapter.id));
    const byId = new Map(volumeFiltered.map(chapter => [chapter.id, chapter]));
    matchedIds.forEach(id => {
      let parentId = byId.get(id)?.parent_id || null;
      while (parentId) {
        matchedIds.add(parentId);
        parentId = byId.get(parentId)?.parent_id || null;
      }
    });
    return volumeFiltered.filter(chapter => matchedIds.has(chapter.id));
  }, [activeVolume, chapters, keyword]);
  const selectedChapter = filteredChapters.find(chapter => chapter.id === selectedId)
    || filteredChapters[0]
    || (activeVolume === 'all' ? chapters.find(chapter => chapter.id === selectedId) || chapters[0] : undefined);
  const visibleChapters = useMemo(
    () => filteredChapters.filter(chapter => isVisibleChapter(chapter, filteredChapters)),
    [filteredChapters],
  );
  const scopedChapters = activeVolume === 'all' ? chapters : chapters.filter(chapter => matchesActiveVolume(chapter, activeVolume));
  const matchText = keyword ? `${filteredChapters.length} / ${scopedChapters.length}` : `0 / ${scopedChapters.length}`;
  const actualChars = scopedChapters.reduce((sum, chapter) => sum + (isChapterGenerated(chapter) ? chapterActualWords(chapter) : 0), 0);
  const estimatedTotalChars = scopedChapters.reduce((sum, chapter) => (
    sum + (isChapterGenerated(chapter) ? chapterActualWords(chapter) : targetChapterWords(chapter))
  ), 0);
  const technicalActualChars = chapters.filter(chapter => deliveryVolumeType(chapter) === 'technical').reduce((sum, chapter) => sum + (isChapterGenerated(chapter) ? chapterActualWords(chapter) : 0), 0);
  const businessActualChars = chapters.filter(chapter => deliveryVolumeType(chapter) === 'business').reduce((sum, chapter) => sum + (isChapterGenerated(chapter) ? chapterActualWords(chapter) : 0), 0);
  const lengthGoalChars = activeVolume === 'technical'
    ? lengthSettings.technicalWords
    : activeVolume === 'business'
      ? lengthSettings.businessWords
      : lengthSettings.technicalWords + lengthSettings.businessWords;
  const lengthGoalPages = activeVolume === 'technical'
    ? lengthSettings.technicalPages
    : activeVolume === 'business'
      ? lengthSettings.businessPages
      : lengthSettings.technicalPages + lengthSettings.businessPages;
  const currentEstimatedPages = activeVolume === 'technical'
    ? Math.max(0, Math.ceil(actualChars / WORDS_PER_PAGE.technical))
    : activeVolume === 'business'
      ? Math.max(0, Math.ceil(actualChars / WORDS_PER_PAGE.business))
      : Math.max(0, Math.ceil(technicalActualChars / WORDS_PER_PAGE.technical) + Math.ceil(businessActualChars / WORDS_PER_PAGE.business));
  const estimatedPages = Math.max(1, Math.ceil(estimatedTotalChars / 700));
  const generatedCount = scopedChapters.filter(isChapterGenerated).length;
  const generationProgress = scopedChapters.length ? Math.round((generatedCount / scopedChapters.length) * 10000) / 100 : 0;
  const lengthProgress = lengthGoalChars ? Math.min(100, Math.round((actualChars / lengthGoalChars) * 10000) / 100) : 0;
  const complianceSummary = complianceReport?.summary || {
    metricName: '条款响应覆盖率',
    scopeNote: '基于招标条款、评分项、风险项与当前章节映射/正文片段的响应追踪结果，不等同于最终 Word 标书合规结论。',
    total: 0,
    covered: 0,
    partial: 0,
    missing: 0,
    percent: 0,
    highRiskMissing: 0,
  };
  const complianceStatus = complianceSummary.highRiskMissing
    ? { label: '高风险未响应', color: 'red' as const }
    : complianceSummary.missing || complianceSummary.partial
      ? { label: '有待补强', color: 'orange' as const }
      : complianceSummary.total
        ? { label: '可下载', color: 'green' as const }
        : { label: '待检查', color: 'default' as const };
  const complianceTimeText = complianceLastCheckedAt
    ? complianceLastCheckedAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : '尚未检查';
  const pendingComplianceRows = (complianceReport?.rows || []).filter(row => row.status !== 'covered');
  const complianceVolumeSummaries = (complianceReport?.volumeSummaries || []).filter(item => item.total > 0 || item.highRiskMissing || item.missing);

  function jumpToComplianceRow(row: ComplianceRow): void {
    const targetId = row.suggestedChapterId || row.matchedChapterId;
    if (!targetId) {
      message.info('当前检查项暂无可定位章节，建议先新增补强章节或补强段落。');
      return;
    }
    const target = chapters.find(chapter => chapter.id === targetId);
    if (!target) {
      message.warning('建议章节不在当前分册视图中，请切换到全部或对应分册后再定位。');
      return;
    }
    setActiveVolume(deliveryVolumeType(target));
    setSelectedId(target.id);
    setMode('正文模式');
    setComplianceDrawerOpen(false);
  }

  async function generateSupplementForRow(row: ComplianceRow): Promise<void> {
    if (!data?.project?.id) {
      message.warning('当前项目不存在，无法生成补强内容');
      return;
    }
    const targetId = row.suggestedChapterId || row.matchedChapterId;
    const target = chapters.find(chapter => chapter.id === targetId);
    if (!target) {
      message.info('当前检查项暂无可补强章节，请先新增或选择补强章节。');
      return;
    }

    setSupplementingRowId(row.id);
    try {
      const result = await generateComplianceSupplement(data.project.id, { row, section: target });
      const supplement = `\n\n### 针对${row.category}的补强响应\n\n${result.content}\n`;
      const nextSection = {
        ...target,
        content: `${target.content || `## ${target.title || '未命名章节'}\n`}${supplement}`,
        status: 'edited',
        order_index: chapters.findIndex(item => item.id === target.id) + 1,
      };
      const saved = await saveBidSection(data.project.id, nextSection);
      setChapters(items => normalizeChapterHierarchy(items.map(item => item.id === target.id ? { ...item, ...saved } : item)));
      setSelectedId(saved.id || target.id);
      setActiveVolume(deliveryVolumeType(target));
      setMode('正文模式');
      setContentDirty(false);
      setComplianceDrawerOpen(false);
      message.success('补强内容已生成并保存到建议章节');
      void refreshComplianceReport(data.project.id, { silent: true, volumeType: deliveryVolumeType(target) });
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setSupplementingRowId('');
    }
  }

  function LengthSettingsModal(): JSX.Element {
    return (
      <Modal
        title="全文生成设置"
        open={lengthSettingsOpen}
        okText="保存并刷新章节目标"
        cancelText="取消"
        confirmLoading={lengthSettingsSaving}
        width={760}
        onOk={() => void saveLengthSettings()}
        onCancel={() => setLengthSettingsOpen(false)}
        destroyOnClose
      >
        <Alert
          className="mb-4"
          type="info"
          showIcon
          message="按技术标和商务标设置目标篇幅"
          description="页数是用户侧主要设置项，系统会换算为目标字数并分配到各章节。资格文件、报价文件和附件材料归入商务标整体控制，但会限制空泛扩写。"
        />
        {lengthFeasibility?.warnings?.length ? (
          <Alert
            className="mb-4"
            type="warning"
            showIcon
            message="当前目标篇幅需要补充支撑材料"
            description={(
              <Space direction="vertical" size={4}>
                {lengthFeasibility.warnings.map(item => <span key={item}>{item}</span>)}
              </Space>
            )}
          />
        ) : null}
        <Form<BidLengthSettings>
          form={lengthForm}
          layout="vertical"
          initialValues={DEFAULT_LENGTH_SETTINGS}
        >
          <Form.Item name="mode" label="设置方式" rules={[{ required: true, message: '请选择设置方式' }]}>
            <Radio.Group
              optionType="button"
              buttonStyle="solid"
              options={[
                { label: '按页数设置', value: 'pages' },
                { label: '按字数设置', value: 'words' },
              ]}
            />
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prev, next) => prev.mode !== next.mode}>
            {({ getFieldValue }) => {
              const mode = getFieldValue('mode') === 'words' ? 'words' : 'pages';
              return mode === 'pages' ? (
                <div className="length-settings-grid">
                  <Form.Item
                    name="technicalPages"
                    label="技术标目标页数"
                    rules={[{ required: true, message: '请输入技术标目标页数' }]}
                  >
                    <InputNumber min={1} max={600} addonAfter="页" className="w-full" />
                  </Form.Item>
                  <Form.Item
                    name="businessPages"
                    label="商务标目标页数"
                    rules={[{ required: true, message: '请输入商务标目标页数' }]}
                  >
                    <InputNumber min={1} max={600} addonAfter="页" className="w-full" />
                  </Form.Item>
                </div>
              ) : (
                <div className="length-settings-grid">
                  <Form.Item
                    name="technicalWords"
                    label="技术标目标字数"
                    rules={[{ required: true, message: '请输入技术标目标字数' }]}
                  >
                    <InputNumber min={1000} max={420000} step={1000} addonAfter="字" className="w-full" />
                  </Form.Item>
                  <Form.Item
                    name="businessWords"
                    label="商务标目标字数"
                    rules={[{ required: true, message: '请输入商务标目标字数' }]}
                  >
                    <InputNumber min={1000} max={330000} step={1000} addonAfter="字" className="w-full" />
                  </Form.Item>
                </div>
              );
            }}
          </Form.Item>

          <Form.Item
            name="allowAutoExpand"
            label="资料不足时的生成策略"
            tooltip="建议选择稳健模式。系统不会为了凑页数虚构证书、业绩、金额、人员或无关段落。"
          >
            <Radio.Group
              options={[
                { label: '稳健生成：不足处使用待补充占位', value: false },
                { label: '允许扩写：仅围绕评分点和可验证措施扩展', value: true },
              ]}
            />
          </Form.Item>

          <Form.Item noStyle shouldUpdate>
            {({ getFieldsValue }) => {
              const preview = normalizeLengthFormValues(getFieldsValue());
              const warnings = localLengthWarnings(preview);
              return (
                <Space direction="vertical" size={10} className="w-full">
                  <div className="length-settings-preview">
                    <span>技术标：{preview.technicalPages} 页 / {preview.technicalWords.toLocaleString()} 字</span>
                    <span>商务标：{preview.businessPages} 页 / {preview.businessWords.toLocaleString()} 字</span>
                    <span>合计：{preview.technicalPages + preview.businessPages} 页 / {(preview.technicalWords + preview.businessWords).toLocaleString()} 字</span>
                  </div>
                  {warnings.length ? (
                    <Alert
                      type="warning"
                      showIcon
                      message="当前目标篇幅偏高"
                      description={(
                        <Space direction="vertical" size={4}>
                          {warnings.map(item => <span key={item}>{item}</span>)}
                        </Space>
                      )}
                    />
                  ) : null}
                </Space>
              );
            }}
          </Form.Item>
        </Form>
      </Modal>
    );
  }

  function QualityDashboard(): JSX.Element {
    if (qualityCollapsed) {
      return (
        <aside className="quality-sidebar quality-sidebar-collapsed">
          <Tooltip title="展开实时质量面板">
            <Button
              type="primary"
              shape="circle"
              icon={<Gauge size={18} />}
              aria-label="展开实时质量面板"
              onClick={() => setQualityCollapsed(false)}
            />
          </Tooltip>
          {complianceSummary.highRiskMissing ? (
            <Tag color="red">{complianceSummary.highRiskMissing}</Tag>
          ) : complianceSummary.missing ? (
            <Tag color="orange">{complianceSummary.missing}</Tag>
          ) : null}
        </aside>
      );
    }

    return (
      <aside className="quality-dashboard quality-sidebar">
        <div className="quality-dashboard-head">
          <div>
            <span>实时质量仪表盘</span>
            <strong>{complianceSummary.volumeName || volumeLabel(activeVolume)}</strong>
          </div>
          <Space size={8} wrap>
            {contentDirty ? <Tag color="gold">正文已修改，保存后更新响应率</Tag> : null}
            {complianceRefreshing ? <Tag color="processing">检查中...</Tag> : null}
            {complianceError ? <Tag color="red">检查失败</Tag> : <Tag color={complianceStatus.color}>{complianceStatus.label}</Tag>}
            <Button size="small" onClick={() => setQualityCollapsed(true)}>
              收起
            </Button>
            <Button
              size="small"
              icon={<RefreshCw size={14} />}
              loading={complianceRefreshing}
              disabled={!data?.project?.id}
              onClick={() => data?.project?.id && void refreshComplianceReport(data.project.id)}
            >
              刷新响应率
            </Button>
            <Button size="small" icon={<Eye size={14} />} disabled={!pendingComplianceRows.length} onClick={() => setComplianceDrawerOpen(true)}>
              查看未响应
            </Button>
            <Button
              size="small"
              type="primary"
              ghost
              icon={<Sparkles size={14} />}
              loading={semanticRefreshing}
              disabled={!data?.project?.id || complianceRefreshing}
              onClick={() => data?.project?.id && void runSemanticReview(data.project.id)}
            >
              语义复核
            </Button>
          </Space>
        </div>
        <div className="quality-dashboard-grid">
          <Tooltip title="当前视图下已生成正文的章节数。章节状态为 generated、edited 或 completed，且正文非空时计入。">
            <article>
              <CheckCircle2 size={18} />
              <span>已生成章节</span>
              <strong>{generatedCount}/{scopedChapters.length}</strong>
            </article>
          </Tooltip>
          <Tooltip title="按当前视图下已生成章节正文去除空白后的字符数估算，用于判断标书厚度和扩写需求。">
            <article>
              <FileText size={18} />
              <span>正文字数</span>
              <strong>{actualChars}</strong>
            </article>
          </Tooltip>
          <Tooltip title={complianceSummary.scopeNote}>
            <article>
              <Gauge size={18} />
              <span>条款响应率</span>
              <strong>{complianceSummary.percent}%</strong>
            </article>
          </Tooltip>
          <Tooltip title="仍未在当前章节映射或正文中找到响应证据的要求条款、评分项和风险项。">
            <article>
              <AlertTriangle size={18} />
              <span>未响应项</span>
              <strong>{complianceSummary.missing}</strong>
            </article>
          </Tooltip>
          <Tooltip title="风险项、否决项、废标项或高优先级条款中仍未找到响应证据的数量。">
            <article>
              <ShieldAlert size={18} />
              <span>高风险未响应</span>
              <strong>{complianceSummary.highRiskMissing || 0}</strong>
            </article>
          </Tooltip>
          <Tooltip title={complianceError || '最近一次条款响应检查完成时间。保存章节或生成正文后会自动刷新。'}>
            <article>
              <Clock3 size={18} />
              <span>最后检查</span>
              <strong>{complianceRefreshing ? '检查中' : complianceTimeText}</strong>
            </article>
          </Tooltip>
        </div>
        {complianceVolumeSummaries.length ? (
          <div className="mt-3 grid gap-2">
            {complianceVolumeSummaries.map(item => (
              <Tooltip
                key={item.volumeType}
                title={`${item.volumeName}：共 ${item.total} 项，已响应 ${item.covered} 项，待补强 ${item.partial} 项，未响应 ${item.missing} 项。`}
              >
                <button
                  type="button"
                  className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-sm hover:border-blue-300 hover:bg-blue-50"
                  onClick={() => {
                    setComplianceDrawerOpen(true);
                  }}
                >
                  <span className="font-semibold text-slate-700">{item.volumeName}</span>
                  <span className="text-slate-500">{item.percent}%</span>
                  {item.highRiskMissing ? <Tag color="red">{item.highRiskMissing} 高风险</Tag> : item.missing ? <Tag color="orange">{item.missing} 未响应</Tag> : <Tag color="green">正常</Tag>}
                </button>
              </Tooltip>
            ))}
          </div>
        ) : null}
      </aside>
    );
  }

  function ComplianceDrawer(): JSX.Element {
    return (
      <Drawer
        title={`未响应与待补强项 - ${complianceSummary.volumeName || volumeLabel(activeVolume)}`}
        width={680}
        open={complianceDrawerOpen}
        onClose={() => setComplianceDrawerOpen(false)}
      >
        <Alert
          type="info"
          showIcon
          className="mb-3"
          message="点击“定位章节”可跳转到建议补强位置。"
          description="建议章节由系统根据条款关键词、章节标题、章节目标和正文内容推断；若无建议章节，通常需要新增补强章节或段落。"
        />
        <List
          dataSource={pendingComplianceRows}
          locale={{ emptyText: '当前范围暂无未响应或待补强项' }}
          renderItem={row => (
            <List.Item
              actions={[
                <Button
                  key="supplement"
                  size="small"
                  type="link"
                  loading={supplementingRowId === row.id}
                  disabled={!row.suggestedChapterId && !row.matchedChapterId}
                  onClick={() => void generateSupplementForRow(row)}
                >
                  生成补强
                </Button>,
                <Button
                  key="jump"
                  size="small"
                  type="link"
                  disabled={!row.suggestedChapterId && !row.matchedChapterId}
                  onClick={() => jumpToComplianceRow(row)}
                >
                  定位章节
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={(
                  <Space size={6} wrap>
                    <Tag color={row.category === '风险项' ? 'red' : row.category === '评分项' ? 'green' : 'blue'}>{row.category}</Tag>
                    <Tag color={row.status === 'missing' ? 'red' : 'orange'}>{row.status === 'missing' ? '未响应' : '待补强'}</Tag>
                    <span>{row.content}</span>
                  </Space>
                )}
                description={(
                  <Space direction="vertical" size={2}>
                    <span>建议补强章节：{row.suggestedChapter || row.matchedChapter || '需新增补强章节/段落'}</span>
                    <span>来源页码：{row.sourcePage ? `第 ${row.sourcePage} 页` : '需复核'}</span>
                  </Space>
                )}
              />
            </List.Item>
          )}
        />
      </Drawer>
    );
  }

  function semanticStatusColor(status: SemanticComplianceReview['status']): 'green' | 'orange' | 'red' {
    if (status === 'covered') return 'green';
    if (status === 'partial') return 'orange';
    return 'red';
  }

  function SemanticComplianceDrawer(): JSX.Element {
    const summary = semanticReport?.summary;
    return (
      <Drawer
        title={`语义合规复核 - ${semanticReport?.volumeName || volumeLabel(activeVolume)}`}
        width={760}
        open={semanticDrawerOpen}
        onClose={() => setSemanticDrawerOpen(false)}
      >
        <Alert
          type="info"
          showIcon
          className="mb-3"
          message={summary ? `复核 ${summary.total} 项，语义覆盖率 ${summary.percent}%` : '语义复核用于检查正文是否实质响应条款'}
          description="系统优先复核高风险项、评分项、未覆盖和待补强项。证据摘录和置信度用于下载前质量把关，不替代人工终审。"
        />
        <List
          dataSource={semanticReport?.reviews || []}
          locale={{ emptyText: '暂无语义复核结果' }}
          renderItem={row => (
            <List.Item
              actions={[
                <Button
                  key="jump"
                  size="small"
                  type="link"
                  disabled={!row.targetSectionId}
                  onClick={() => {
                    const target = chapters.find(chapter => chapter.id === row.targetSectionId);
                    if (!target) {
                      message.warning('建议章节不在当前目录中，请刷新后重试。');
                      return;
                    }
                    setSelectedId(target.id);
                    setActiveVolume(deliveryVolumeType(target));
                    setMode('正文模式');
                    setSemanticDrawerOpen(false);
                  }}
                >
                  定位章节
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={(
                  <Space size={6} wrap>
                    <Tag color={row.category === '风险项' ? 'red' : row.category === '评分项' ? 'green' : 'blue'}>{row.category}</Tag>
                    <Tag color={semanticStatusColor(row.status)}>{row.status === 'covered' ? '已覆盖' : row.status === 'partial' ? '部分覆盖' : '未覆盖'}</Tag>
                    <Tag color="purple">置信度 {Math.round((row.confidence || 0) * 100)}%</Tag>
                    <Tag>{row.weight}</Tag>
                    {row.llmReviewed ? <Tag color="geekblue">LLM</Tag> : <Tag>规则兜底</Tag>}
                  </Space>
                )}
                description={(
                  <Space direction="vertical" size={4}>
                    <span>建议章节：{row.targetSectionTitle || '需新增或人工定位'}</span>
                    <span>证据摘录：{row.evidence || '未找到可直接引用的正文证据'}</span>
                    <span>补强建议：{row.suggestion}</span>
                  </Space>
                )}
              />
            </List.Item>
          )}
        />
      </Drawer>
    );
  }

  function chapterActualWords(chapter: ChapterDraft): number {
    return (chapter.content || '').replace(/\s+/g, '').length;
  }

  function fallbackChapterWords(chapter: ChapterDraft): number {
    return Math.max(420, Math.min(1200, Math.round(((chapter.level || 1) <= 2 ? 680 : 520) / 10) * 10));
  }

  function chapterWritingPlan(chapter: ChapterDraft): ChapterWritingPlan {
    const metadata = chapter.metadata || {};
    const plan = metadata.writing_plan;
    if (plan && typeof plan === 'object') {
      return plan as ChapterWritingPlan;
    }
    const title = `${chapter.title || ''} ${chapter.purpose || ''}`;
    const isTechnical = /技术|施工组织|实施方案|质量|安全|环保|进度|发包人要求|承包人建议/.test(title);
    const isQualification = /资格|资质|证书|营业执照|人员|项目经理|技术负责人/.test(title);
    const isFormat = /投标函|格式|授权|保证金|声明|承诺|偏离/.test(title);
    const targetWords = isTechnical ? ((chapter.level || 1) <= 2 ? 6200 : 2800) : isQualification ? 2600 : isFormat ? 900 : fallbackChapterWords(chapter);
    return {
      importance: chapter.priority || (isTechnical || isQualification ? 'high' : 'medium'),
      target_words: targetWords,
      suggested_pages: `${Math.max(1, Math.round(targetWords / 900))}-${Math.max(1, Math.round(targetWords / 650))}`,
      needs_table: /报价|清单|人员|业绩|偏离|进度|参数|评分/.test(title),
      needs_image: isTechnical || /设备|产品|工艺|流程|布置/.test(title),
      needs_qualification: isQualification,
      needs_case: /业绩|案例|类似项目|施工组织|技术|质量|安全/.test(title),
      generation_mode: targetWords >= 3500 ? 'multi_pass' : 'single_pass',
    };
  }

  function targetChapterWords(chapter: ChapterDraft): number {
    const targetWords = chapterWritingPlan(chapter).target_words;
    return typeof targetWords === 'number' && Number.isFinite(targetWords) ? targetWords : fallbackChapterWords(chapter);
  }

  function isChapterFailed(chapter: ChapterDraft): boolean {
    const task = batchTasks[chapter.id];
    if (['generated', 'edited', 'completed'].includes(chapter.status || '')) return false;
    if (task?.status === 'queued' || task?.status === 'running' || task?.status === 'done') return false;
    return task?.status === 'failed' || chapter.status === 'failed';
  }

  function chapterWordMeta(chapter: ChapterDraft): { label: string; tooltip: string; generated: boolean; failed: boolean } {
    if (isChapterFailed(chapter)) {
      return {
        label: '生成失败',
        tooltip: '本章节正文生成失败，请点击“重写正文”重新生成。',
        generated: false,
        failed: true,
      };
    }
    const generated = isChapterGenerated(chapter);
    if (generated) {
      const actualWords = chapterActualWords(chapter);
      const targetWords = targetChapterWords(chapter);
      if (actualWords < targetWords * 0.75) {
        return {
          label: `建议扩写 ${actualWords}/${targetWords}字`,
          tooltip: `当前正文低于目标字数 75%。建议结合评分点、风险项和企业资料补充，不要用重复或无关内容凑字数。`,
          generated: true,
          failed: false,
        };
      }
      if (actualWords > targetWords * 1.35) {
        return {
          label: `篇幅偏长 ${actualWords}/${targetWords}字`,
          tooltip: `当前正文明显超过目标字数。建议复核是否存在重复段落、无关内容或格式性材料过度展开。`,
          generated: true,
          failed: false,
        };
      }
      return {
        label: `已完成 ${actualWords}字`,
        tooltip: `已完成字数：按当前章节正文去除空白后统计。计划目标：${targetWords}字。`,
        generated: true,
        failed: false,
      };
    }
    return {
      label: `目标 ${targetChapterWords(chapter)}字`,
      tooltip: chapterWritingPlan(chapter).length_settings_source === 'project_length_settings'
        ? `目标字数已由全文生成设置分配；资料不足策略：${chapterWritingPlan(chapter).allow_auto_expand ? '允许围绕评分点和可验证措施扩写' : '稳健生成，缺失处使用待补充占位'}。`
        : '目标字数：来自章节写作计划；如当前项目尚未保存计划，则按章节标题、层级和用途临时推导。',
      generated: false,
      failed: false,
    };
  }

  function chapterImportanceLabel(plan: ChapterWritingPlan): string {
    if (plan.importance === 'high') return '核心章节';
    if (plan.importance === 'low') return '普通章节';
    return '重点章节';
  }

  function batchStatusLabel(status: BatchTaskStatus): string {
    if (status === 'queued') return '排队中';
    if (status === 'running') return '正在编写';
    if (status === 'done') return '已完成';
    if (status === 'stopped') return '已停止';
    return '失败';
  }

  function batchStatusColor(status: BatchTaskStatus): 'default' | 'processing' | 'success' | 'error' {
    if (status === 'running') return 'processing';
    if (status === 'done') return 'success';
    if (status === 'failed') return 'error';
    return 'default';
  }

  function visibleBatchTask(chapter: ChapterDraft): BatchTask | undefined {
    if (isChapterGenerated(chapter)) {
      return undefined;
    }
    return batchTasks[chapter.id];
  }

  function chapterStatusClass(chapter: ChapterDraft): string {
    if (isChapterGenerated(chapter)) return 'done';
    const task = batchTasks[chapter.id];
    if (chapter.status === 'generating') return 'running';
    if (task?.status === 'running') return 'running';
    if (isChapterFailed(chapter)) return 'failed';
    if (task?.status === 'done') return 'done';
    if (task?.status === 'stopped') return 'pending';
    return 'pending';
  }

  function isChapterGenerated(chapter: ChapterDraft): boolean {
    if (isChapterFailed(chapter)) return false;
    const status = chapter.status || '';
    if (!['generated', 'edited', 'completed'].includes(status)) return false;
    const content = (chapter.content || '').trim();
    return !!content && !content.includes('请在此编写章节内容') && !content.includes('待进一步生成正文');
  }

  function isChapterUnderTarget(chapter: ChapterDraft): boolean {
    if (!isChapterGenerated(chapter)) {
      return false;
    }
    return chapterActualWords(chapter) < targetChapterWords(chapter) * 0.75;
  }

  function needsBatchWriting(chapter: ChapterDraft): boolean {
    return !isChapterGenerated(chapter) || isChapterUnderTarget(chapter);
  }

  function downloadOutlineMarkdown(): void {
    const source = visibleChapters.length ? visibleChapters : scopedChapters;
    if (!source.length) {
      message.warning('当前没有可下载的目录');
      return;
    }
    const title = `${volumeLabel(activeVolume)}目录`;
    const lines = [
      `# ${title}`,
      '',
      ...source.map(chapter => {
        const level = Math.max(1, Math.min(chapter.level || 1, 6));
        return `${'#'.repeat(level + 1)} ${chapterDisplayTitle(chapter)}`;
      }),
      '',
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${title}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function chapterIndent(level?: number): number {
    return 12 + Math.max(0, Math.min((level || 1) - 1, 3)) * 20;
  }

  function collectDescendantIds(source: ChapterDraft[], rootId: string): Set<string> {
    const descendants = new Set<string>([rootId]);
    let changed = true;
    while (changed) {
      changed = false;
      source.forEach(item => {
        if (item.parent_id && descendants.has(item.parent_id) && !descendants.has(item.id)) {
          descendants.add(item.id);
          changed = true;
        }
      });
    }
    return descendants;
  }

  function syncChapterOrder(nextChapters: ChapterDraft[]): Promise<void> | void {
    if (!data?.project?.id) {
      return;
    }
    return reorderBidSections(
      data.project.id,
      nextChapters
        .filter(item => isUuid(item.id))
        .map((item, index) => ({
          id: item.id,
          parent_id: safeParentIdForSave(item.parent_id, nextChapters),
          level: item.level || 1,
          order_index: index + 1,
        })),
    ).then(() => {
      setChapters(normalizeChapterHierarchy(nextChapters));
    });
  }

  function isVisibleChapter(chapter: ChapterDraft, pool: ChapterDraft[]): boolean {
    const byId = new Map(pool.map(item => [item.id, item]));
    let parentId = chapter.parent_id || null;
    while (parentId) {
      const parent = byId.get(parentId);
      if (!parent) {
        break;
      }
      if (!parent.expanded) {
        return false;
      }
      parentId = parent.parent_id || null;
    }
    return true;
  }

  function siblingChapters(chapter: ChapterDraft, source = chapters): ChapterDraft[] {
    return source.filter(item => (item.parent_id || null) === (chapter.parent_id || null));
  }

  function canMoveChapter(chapter: ChapterDraft, direction: 'up' | 'down'): boolean {
    const siblings = siblingChapters(chapter);
    const index = siblings.findIndex(item => item.id === chapter.id);
    if (index < 0) {
      return false;
    }
    return direction === 'up' ? index > 0 : index < siblings.length - 1;
  }

  async function moveChapter(chapter: ChapterDraft, direction: 'up' | 'down'): Promise<void> {
    const siblings = siblingChapters(chapter, chapters);
    const siblingIndex = siblings.findIndex(item => item.id === chapter.id);
    if (siblingIndex < 0) {
      return;
    }
    const targetSibling = direction === 'up' ? siblings[siblingIndex - 1] : siblings[siblingIndex + 1];
    if (!targetSibling) {
      return;
    }

    const currentIds = collectDescendantIds(chapters, chapter.id);
    const targetIds = collectDescendantIds(chapters, targetSibling.id);
    const currentBlock = chapters.filter(item => currentIds.has(item.id));
    const targetBlock = chapters.filter(item => targetIds.has(item.id));
    const currentStart = chapters.findIndex(item => item.id === currentBlock[0]?.id);
    const targetStart = chapters.findIndex(item => item.id === targetBlock[0]?.id);
    if (currentStart < 0 || targetStart < 0) {
      return;
    }

    const withoutBlocks = chapters.filter(item => !currentIds.has(item.id) && !targetIds.has(item.id));
    const insertAt = Math.min(currentStart, targetStart);
    const reorderedBlocks = direction === 'up'
      ? [...currentBlock, ...targetBlock]
      : [...targetBlock, ...currentBlock];
    const nextChapters = normalizeChapterHierarchy([
      ...withoutBlocks.slice(0, insertAt),
      ...reorderedBlocks,
      ...withoutBlocks.slice(insertAt),
    ]);

    setChapters(nextChapters);
    try {
      await syncChapterOrder(nextChapters);
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
      void reloadProject(data?.project?.id || '');
    }
  }

  function createBlankChapter(order: number, title = '新增章节', parent?: ChapterDraft | null): ChapterDraft {
    return {
      id: `${order}-${title}-${Date.now()}`,
      order,
      order_index: order,
      parent_id: parent?.id || null,
      level: Math.min((parent?.level || 0) + 1 || 1, 4),
      title,
      priority: 'medium',
      purpose: '请补充本章编写目标。',
      response_points: ['请补充响应要点。'],
      mapped_requirements: [],
      mapped_scoring_items: [],
      mapped_risks: [],
      source_pages: [],
      required_materials: [],
      writing_notes: ['新增章节后建议先关联招标要求，再生成正文。'],
      content: `## ${title}\n\n请在此编写章节内容。`,
      expanded: true,
    };
  }

  function lastDescendantIndex(items: ChapterDraft[], parentId: string): number {
    const idSet = new Set<string>([parentId]);
    let lastIndex = items.findIndex(item => item.id === parentId);
    for (let index = lastIndex + 1; index < items.length; index += 1) {
      const item = items[index];
      if (item.parent_id && idSet.has(item.parent_id)) {
        idSet.add(item.id);
        lastIndex = index;
        continue;
      }
      if (item.level && (items[lastIndex]?.level || 1) < item.level && item.parent_id && idSet.has(item.parent_id)) {
        idSet.add(item.id);
        lastIndex = index;
        continue;
      }
      if ((item.level || 1) <= (items.find(node => node.id === parentId)?.level || 1)) {
        break;
      }
    }
    return Math.max(lastIndex, items.findIndex(item => item.id === parentId));
  }

  async function addChapter(options?: AddChapterOptions): Promise<void> {
    const parent = options?.parent || null;
    const chapter = createBlankChapter(chapters.length + 1, '新增章节', parent);
    const nextChapters = (() => {
      if (!parent) {
        return normalizeChapterHierarchy([...chapters, chapter]);
      }
      const insertAfter = lastDescendantIndex(chapters, parent.id);
      const nextItems = [...chapters];
      nextItems.splice(insertAfter + 1, 0, chapter);
      return normalizeChapterHierarchy(nextItems);
    })();
    setChapters(nextChapters);
    setSelectedId(chapter.id);
    if (data?.project?.id) {
      try {
        const saved = await saveBidSection(data.project.id, {
          ...chapter,
          parent_id: safeParentIdForSave(parent?.id || null, chapters),
          level: chapter.level || 1,
          order_index: nextChapters.findIndex(item => item.id === chapter.id) + 1,
        });
        setChapters(items => normalizeChapterHierarchy(items.map(item => item.id === chapter.id ? { ...item, ...saved } : item)));
        setSelectedId(saved.id);
      } catch (error) {
        message.error(error instanceof Error ? error.message : String(error));
      }
    }
  }

  function toggleChapter(id: string): void {
    setChapters(items => items.map(item => item.id === id ? { ...item, expanded: !item.expanded } : item));
  }

  function setAllExpanded(expanded: boolean): void {
    setChapters(items => items.map(item => ({ ...item, expanded })));
  }

  function previewChapter(chapter: ChapterDraft): void {
    setSelectedId(chapter.id);
    setMode('正文模式');
  }

  async function saveDraft(): Promise<void> {
    if (!data?.project?.id || !selectedChapter) {
      message.warning('请先选择需要保存的章节');
      return;
    }
    try {
      const saved = await saveBidSection(data.project.id, {
        ...selectedChapter,
        parent_id: safeParentIdForSave(selectedChapter.parent_id, chapters),
        level: selectedChapter.level || 1,
        order_index: chapters.findIndex(item => item.id === selectedChapter.id) + 1,
        status: selectedChapter.status || 'edited',
      });
      setChapters(items => normalizeChapterHierarchy(items.map(item => item.id === selectedChapter.id ? { ...item, ...saved } : item)));
      setSelectedId(saved.id);
      setContentDirty(false);
      message.success('章节已保存到 Supabase');
      setDownloadUrl('');
      void refreshComplianceReport(data.project.id, { silent: true });
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function confirmDownloadWithCompliance(projectId: string, volumeType?: VolumeType): Promise<boolean> {
    let report: ComplianceReport;
    try {
      report = await getComplianceCheck(projectId, {
        volumeType: complianceVolumeParam(volumeType),
      });
    } catch (error) {
      message.warning(error instanceof Error ? `条款响应检查失败：${error.message}` : '条款响应检查失败，仍可继续下载。');
      return true;
    }

    const summary = report.summary;
    if (!summary.missing && !summary.highRiskMissing) {
      return true;
    }

    return new Promise(resolve => {
      Modal.confirm({
        title: `下载前条款响应检查：${summary.volumeName || volumeLabel(volumeType || 'all')}`,
        okText: '继续下载',
        cancelText: '返回补强',
        width: 560,
        content: (
          <div className="space-y-3 text-sm">
            <Alert
              type="warning"
              showIcon
              message={`${summary.metricName || '条款响应覆盖率'} ${summary.percent}%`}
              description={summary.scopeNote || '该指标用于追踪招标条款与当前章节/正文的响应关系，不等同于最终 Word 标书合规结论。'}
            />
            <div className="grid grid-cols-2 gap-2">
              <Tag color="blue">共检查 {summary.total} 项</Tag>
              <Tag color="green">已响应 {summary.covered} 项</Tag>
              <Tag color="orange">待补强 {summary.partial} 项</Tag>
              <Tag color="red">未响应 {summary.missing} 项</Tag>
            </div>
            <p className="text-slate-600">
              当前仍有 {summary.highRiskMissing || 0} 项高风险未响应。建议优先补齐资格要求、否决风险和高分评分项后再提交正式投标文件。
            </p>
          </div>
        ),
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });
  }

  async function downloadDocx(sectionId?: string): Promise<void> {
    if (!data?.project?.id) {
      message.warning('当前项目不存在，无法下载');
      return;
    }
    if (!sectionId) {
      const confirmed = await confirmDownloadWithCompliance(data.project.id, activeVolume);
      if (!confirmed) {
        message.info('已取消下载，请先处理条款响应补强项。');
        return;
      }
    }
    setDownloadGenerating(sectionId ? 'section' : 'full');
    setExportTask(null);
    try {
      const sectionsSnapshot = chapters.map((chapter, index) => ({
        ...chapter,
        order_index: index + 1,
        level: chapter.level || 1,
        parent_id: chapter.parent_id || null,
        content: chapter.content || '',
      }));
      const result = await generateBidDocxDownload(data.project.id, {
        sectionId,
        withImages: !sectionId && withImages,
        volumeType: !sectionId && activeVolume !== 'all' ? activeVolume : undefined,
        sectionsSnapshot,
      });
      setExportTask(result.task);
      message.info(sectionId ? '本章 DOCX 导出任务已创建' : `${activeVolume === 'all' ? '全文' : volumeLabel(activeVolume)} DOCX 导出任务已创建`);
      await pollBidExportTask(data.project.id, result.taskId, sectionId ? 'section' : 'full');
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setDownloadGenerating(null);
    }
  }

  async function pollBidExportTask(projectId: string, taskId: string, scope: 'full' | 'section'): Promise<void> {
    const maxAttempts = 180;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const task = await getBidExportTask(projectId, taskId);
      setExportTask(task);
      if (task.status === 'completed') {
        if (!task.download_url) {
          throw new Error('DOCX 导出完成但未返回下载地址');
        }
        setDownloadUrl(task.download_url);
        window.open(task.download_url, '_blank');
        const imageConversion = task.metadata?.image_conversion;
        const imageSelection = task.metadata?.image_selection;
        const failedImages = Number(imageConversion?.failed || 0);
        const skippedImages = Number(imageConversion?.skipped || 0);
        const insertedImages = Number(imageConversion?.inserted || 0);
        const selectionWarnings = imageSelection?.warnings || [];
        if (failedImages > 0 || skippedImages > 0 || selectionWarnings.length > 0) {
          message.warning(`DOCX 已生成，图片插入 ${insertedImages} 张，跳过 ${skippedImages} 张，失败 ${failedImages} 张，请下载后复核图文位置。`, 7);
        } else {
          message.success(scope === 'section' ? '本章 DOCX 已生成' : `${activeVolume === 'all' ? '全文' : volumeLabel(activeVolume)} DOCX 已生成`);
        }
        return;
      }
      if (task.status === 'failed') {
        throw new Error(task.error_message || task.message || 'DOCX 导出失败');
      }
      await new Promise(resolve => window.setTimeout(resolve, 1500));
    }
    throw new Error('DOCX 导出仍在处理中，请稍后刷新任务状态或重试。');
  }

  async function resetGenerationStatus(): Promise<void> {
    if (!data?.project?.id) {
      message.warning('当前项目不存在，无法重置');
      return;
    }
    setResettingGeneration(true);
    try {
      const saved = await resetBidSectionsGeneration(data.project.id, resetClearContent);
      const savedById = new Map(saved.map(section => [section.id, section]));
      setChapters(items => normalizeChapterHierarchy(items.map(item => {
        const savedItem = savedById.get(item.id);
        return {
          ...item,
          ...(savedItem || {}),
          status: 'draft',
          content: resetClearContent ? '' : (savedItem?.content ?? item.content),
        };
      })));
      setBatchTasks({});
      setDownloadUrl('');
      setResetModalOpen(false);
      message.success(resetClearContent ? '已重置全部章节状态，并清空正文' : '已重置全部章节生成状态');
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setResettingGeneration(false);
    }
  }

  function appendChapterContent(chapterId: string, value: string): void {
    setChapters(items => items.map(item => item.id === chapterId ? { ...item, content: `${item.content}${value}` } : item));
  }

  function updateBatchTask(chapterId: string, patch: Partial<BatchTask>): void {
    setBatchTasks(tasks => ({
      ...tasks,
      [chapterId]: {
        ...(tasks[chapterId] || {
          status: 'queued',
          percent: 0,
          chars: 0,
          targetWords: 800,
        }),
        ...patch,
      },
    }));
  }

  function syncBatchTaskItem(chapterId: string, patch: Partial<BatchTask> & { error?: string; saved_section_id?: string }): Promise<void> {
    const taskId = persistedBatchTaskIdRef.current || persistedBatchTask?.id;
    if (!data?.project?.id || !taskId) {
      return Promise.resolve();
    }
    const now = Date.now();
    const lastSyncAt = batchTaskSyncAtRef.current.get(chapterId) || 0;
    if (patch.status === 'running' && now - lastSyncAt < 5000) {
      return Promise.resolve();
    }
    batchTaskSyncAtRef.current.set(chapterId, now);
    const payload = {
      status: patch.status,
      percent: patch.percent,
      chars: patch.chars,
      target_words: patch.targetWords,
      message: patch.message,
      error: patch.error,
      saved_section_id: patch.saved_section_id,
    };
    return updateSectionGenerationTaskItem(data.project.id, taskId, chapterId, payload).then(task => {
      setPersistedBatchTask({ id: task.id, status: task.status });
      persistedBatchTaskIdRef.current = task.id;
    }).catch(error => {
      console.warn('同步批量章节生成任务状态失败', error);
    });
  }

  function renameChapter(chapter: ChapterDraft): void {
    let nextTitle = chapter.title || '';
    Modal.confirm({
      title: '修改章节标题',
      content: (
        <Input
          defaultValue={chapter.title}
          autoFocus
          onChange={event => {
            nextTitle = event.target.value;
          }}
        />
      ),
      okText: '保存',
      cancelText: '取消',
      onOk: async () => {
        const title = nextTitle.trim();
        if (!title) {
          message.warning('章节标题不能为空');
          return Promise.reject();
        }
        const renamed = {
          ...chapter,
          title,
          content: chapter.content.replace(/^## .*/m, `## ${title}`),
          parent_id: safeParentIdForSave(chapter.parent_id, chapters),
          order_index: chapters.findIndex(item => item.id === chapter.id) + 1,
          status: 'edited',
        };
        if (data?.project?.id) {
          await saveBidSection(data.project.id, renamed);
        }
        setChapters(items => normalizeChapterHierarchy(items.map(item => item.id === chapter.id ? {
          ...item,
          title,
          content: item.content.replace(/^## .*/m, `## ${title}`),
        } : item)));
      },
    });
  }

  function deleteChapter(chapter: ChapterDraft): void {
    Modal.confirm({
      title: '删除章节',
      content: `确认删除“${chapter.title || '未命名章节'}”？此操作只影响当前页面草稿。`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        if (data?.project?.id && chapter.id && isUuid(chapter.id)) {
          await deleteBidSection(data.project.id, chapter.id);
        }
        setChapters(items => {
          const descendants = new Set<string>([chapter.id]);
          let changed = true;
          while (changed) {
            changed = false;
            items.forEach(item => {
              if (item.parent_id && descendants.has(item.parent_id) && !descendants.has(item.id)) {
                descendants.add(item.id);
                changed = true;
              }
            });
          }
          const nextItems = normalizeChapterHierarchy(items.filter(item => !descendants.has(item.id)));
          if (selectedId === chapter.id) {
            setSelectedId(nextItems[0]?.id || '');
          }
          return nextItems;
        });
      },
    });
  }

  function customWritingPlaceholder(chapter: ChapterDraft): string {
    const title = `${chapter.title || ''} ${chapter.purpose || ''} ${(chapter.response_points || []).join(' ')}`;
    const plan = chapterWritingPlan(chapter);
    const compact = (items?: unknown[], limit = 2): string => (items || [])
      .map(item => String(item || '').trim())
      .filter(Boolean)
      .slice(0, limit)
      .join('、');
    const responseHint = compact(chapter.response_points, 2);
    const scoringHint = compact(chapter.mapped_scoring_items, 2);
    const riskHint = compact(chapter.mapped_risks, 2);
    const materialHint = compact(chapter.required_materials, 2);
    if (/安全|应急|文明施工|生产/.test(title)) {
      return '请输入本章补充要求，例如：补齐安全生产责任体系、危险源辨识、班前教育、应急预案、特种作业管理和安全检查闭环；结合本项目施工风险写具体措施。';
    }
    if (/质量|检验|检测|验收|试验/.test(title)) {
      return '请输入本章补充要求，例如：补齐质量保证体系、工序检验、材料进场复验、隐蔽工程验收、第三方检测和质量问题整改闭环。';
    }
    if (/进度|工期|计划|节点/.test(title)) {
      return '请输入本章补充要求，例如：补齐总进度计划、关键线路、节点工期、资源投入、雨季影响应对和进度偏差纠偏措施。';
    }
    if (/环保|水保|扬尘|噪声|绿色/.test(title)) {
      return '请输入本章补充要求，例如：补齐扬尘控制、噪声控制、废水泥浆处置、水土保持、生态保护和环保监测记录要求。';
    }
    if (/设备|机械|材料|资源/.test(title)) {
      return '请输入本章补充要求，例如：补齐主要设备配置、设备参数、进退场计划、维护保养、备件保障和关键工序设备适配说明。';
    }
    if (/施工方案|施工组织|工艺|防渗|灌浆|旋喷/.test(title)) {
      return '请输入本章补充要求，例如：补齐施工流程、关键工艺参数、现场布置、质量控制点、施工难点、风险应对和可量化验收标准。';
    }
    if (/资格|资质|证书|人员|项目经理|技术负责人|业绩/.test(title) || plan.needs_qualification) {
      return '请输入本章补充要求，例如：补齐资质证书、人员证书、类似业绩、社保或任职证明的附件索引；敏感编号和日期使用待补充占位。';
    }
    if (/商务|合同|付款|履约|服务|承诺|偏离|投标函/.test(title)) {
      return '请输入本章补充要求，例如：补齐商务条款响应、付款和履约承诺、偏离说明、服务保障、保密廉政承诺和人工复核占位。';
    }
    if (/报价|清单|价格|单价|工程量/.test(title)) {
      return '请输入本章补充要求，例如：补齐报价口径、工程量清单复核、税费说明、风险边界和人工复核提示；不得编造金额、单价和工程量。';
    }
    if (plan.needs_table) {
      return '请输入本章补充要求，例如：补齐可量化承诺、表格字段、责任部门、完成时限、证明材料索引和人工复核说明。';
    }
    if (plan.needs_case) {
      return '请输入本章补充要求，例如：结合类似项目经验补充做法、成效、适用条件和证明材料索引；缺少业绩事实时使用待补充占位。';
    }
    return [
      `请输入「${chapter.title || '本章'}」的补充要求。`,
      responseHint ? `可围绕响应要点：${responseHint}。` : '',
      scoringHint ? `重点补强评分项：${scoringHint}。` : '',
      riskHint ? `注意回应风险点：${riskHint}。` : '',
      materialHint ? `建议补充材料索引：${materialHint}。` : '',
      plan.needs_table ? '如适合，请要求补充表格字段、责任部门、完成时限和可量化承诺。' : '',
      plan.needs_image ? '如适合，请要求补充流程图、设备图、现场布置图或附件图片说明。' : '',
      '不要编造证书编号、人员姓名、金额、日期或未提供的业绩事实。',
    ].filter(Boolean).join(' ');
  }

  function customWriteChapter(chapter: ChapterDraft): void {
    let instruction = '';
    const placeholder = customWritingPlaceholder(chapter);
    Modal.confirm({
      title: `自定义编写：${chapter.title || '未命名章节'}`,
      content: (
        <Input.TextArea
          rows={5}
          placeholder={placeholder}
          onChange={event => {
            instruction = event.target.value;
          }}
        />
      ),
      okText: '加入写作要求',
      cancelText: '取消',
      onOk: () => {
        setChapters(items => items.map(item => item.id === chapter.id ? {
          ...item,
          writing_notes: [...(item.writing_notes || []), instruction.trim() || '按用户自定义要求编写。'],
        } : item));
        setSelectedId(chapter.id);
        message.success('已加入自定义写作要求，可点击生成本章正文');
      },
    });
  }

  function chapterMenuItems(chapter: ChapterDraft): MenuProps['items'] {
    return [
      { key: 'write', label: '编写章节' },
      { key: 'custom', label: '自定义编写' },
      { key: 'add', label: '添加章节' },
      { key: 'move-up', label: '上移章节', icon: <ArrowUp size={14} />, disabled: !canMoveChapter(chapter, 'up') },
      { key: 'move-down', label: '下移章节', icon: <ArrowDown size={14} />, disabled: !canMoveChapter(chapter, 'down') },
      { key: 'rename', label: '修改标题' },
      { type: 'divider' },
      { key: 'delete', label: '删除章节', danger: true },
    ];
  }

  function outlineMoreMenuItems(chapter: ChapterDraft): MenuProps['items'] {
    return [
      { key: 'custom', label: '自定义编写' },
      { key: 'add', label: '新增子章节', icon: <Plus size={14} /> },
      { key: 'rename', label: '修改标题' },
      { key: 'move-up', label: '上移章节', icon: <ArrowUp size={14} />, disabled: !canMoveChapter(chapter, 'up') },
      { key: 'move-down', label: '下移章节', icon: <ArrowDown size={14} />, disabled: !canMoveChapter(chapter, 'down') },
      { type: 'divider' },
      { key: 'delete', label: '删除章节', icon: <Trash2 size={14} />, danger: true },
    ];
  }

  function handleChapterMenu(key: string, chapter: ChapterDraft): void {
    setSelectedId(chapter.id);
    if (key === 'write') {
      void generateCurrentSection(chapter);
    }
    if (key === 'custom') {
      customWriteChapter(chapter);
    }
    if (key === 'add') {
      void addChapter({ parent: chapter });
    }
    if (key === 'rename') {
      renameChapter(chapter);
    }
    if (key === 'move-up') {
      void moveChapter(chapter, 'up');
    }
    if (key === 'move-down') {
      void moveChapter(chapter, 'down');
    }
    if (key === 'delete') {
      deleteChapter(chapter);
    }
  }

  async function streamSectionContent(
    targetChapter: ChapterDraft,
    options?: {
      onStart?: (title?: string) => void;
      onChunk?: (content: string, accumulatedContent: string) => void;
      onDone?: () => void;
      signal?: AbortSignal;
    },
  ): Promise<void> {
    if (!data?.project?.id) {
      throw new Error('当前项目不存在，无法生成章节正文');
    }

    const response = await fetch(`/api/bidding/interpretations/${data.project.id}/sections/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ...targetChapter, withImages }),
      signal: options?.signal,
    });
    if (!response.ok || !response.body) {
      throw new Error(`章节正文生成失败：${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let accumulatedContent = `## ${targetChapter.title || '未命名章节'}\n\n`;
    setChapters(items => items.map(item => item.id === targetChapter.id ? { ...item, content: accumulatedContent } : item));

    function handleFrame(frame: string): void {
      const eventLine = frame.split('\n').find(line => line.startsWith('event:'));
      const dataLine = frame.split('\n').find(line => line.startsWith('data:'));
      const eventName = eventLine?.replace('event:', '').trim() || 'message';
      const dataText = dataLine?.replace('data:', '').trim();
      if (!dataText) {
        return;
      }
      const payload = JSON.parse(dataText) as { content?: string; error?: string; title?: string; id?: string; oldId?: string };
      if (eventName === 'start') {
        options?.onStart?.(payload.title);
      }
      if (eventName === 'chunk' && payload.content) {
        accumulatedContent += payload.content;
        appendChapterContent(targetChapter.id, payload.content);
        options?.onChunk?.(payload.content, accumulatedContent);
      }
      if (eventName === 'done') {
        options?.onDone?.();
      }
      if (eventName === 'saved' && payload.id && payload.oldId && payload.id !== payload.oldId) {
        const savedId = payload.id;
        const oldId = payload.oldId;
        setChapters(items => items.map(item => item.id === oldId ? { ...item, id: savedId, status: 'generated' } : item));
        setSelectedId(current => current === oldId ? savedId : current);
      }
      if (eventName === 'error') {
        throw new Error(payload.error || '章节正文生成失败');
      }
    }

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split('\n\n');
      buffer = frames.pop() || '';
      frames.forEach(handleFrame);
    }
    if (buffer.trim()) {
      handleFrame(buffer);
    }
  }

  async function generateCurrentSection(targetChapter = selectedChapter, options?: { preserveMode?: boolean }): Promise<void> {
    if (!data?.project?.id || !targetChapter) {
      message.warning('请先选择需要生成正文的章节');
      return;
    }
    if (batchGenerating) {
      message.warning('全文批量编写正在执行，请等待完成后再单章重写');
      return;
    }
    if (!options?.preserveMode) {
      setMode('正文模式');
    }
    setSelectedId(targetChapter.id);
    setBatchTasks(tasks => {
      const next = { ...tasks };
      delete next[targetChapter.id];
      return next;
    });
    setSectionStreaming(true);
    setStreamText(`正在生成章节正文：${targetChapter.title || '未命名章节'}`);
    const originalContent = targetChapter.content || '';
    setChapters(items => items.map(item => item.id === targetChapter.id ? { ...item, status: 'generating' } : item));

    try {
      await streamSectionContent(targetChapter, {
        onStart: title => {
          setStreamText(`AI 正在撰写：${title || targetChapter.title || '当前章节'}`);
        },
        onDone: () => {
          setStreamText('章节正文生成完成，可继续人工编辑。');
          setChapters(items => items.map(item => item.id === targetChapter.id ? { ...item, status: 'generated' } : item));
          setBatchTasks(tasks => {
            const next = { ...tasks };
            delete next[targetChapter.id];
            return next;
          });
        },
      });
      message.success('章节正文已生成');
      setContentDirty(false);
      void refreshComplianceReport(data.project.id, { silent: true });
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      setChapters(items => items.map(item => item.id === targetChapter.id ? { ...item, status: 'failed', content: originalContent } : item));
      message.error(`${reason}，已保留原正文`);
    } finally {
      setSectionStreaming(false);
    }
  }

  async function generateSectionForBatch(chapter: ChapterDraft): Promise<void> {
    if (batchCancelRequestedRef.current) {
      updateBatchTask(chapter.id, {
        status: 'stopped',
        percent: 0,
        message: '已停止',
      });
      await syncBatchTaskItem(chapter.id, {
        status: 'stopped',
        message: '已停止',
      });
      return;
    }
    const targetWords = targetChapterWords(chapter);
    const originalContent = chapter.content || '';
    const controller = new AbortController();
    const finalSyncs: Promise<void>[] = [];
    batchAbortControllersRef.current.set(chapter.id, controller);
    updateBatchTask(chapter.id, {
      status: 'running',
      percent: 2,
      chars: 0,
      targetWords,
      message: '正在编写',
    });
    void syncBatchTaskItem(chapter.id, {
      status: 'running',
      percent: 2,
      chars: 0,
      targetWords,
      message: '正在编写',
    });
    setChapters(items => items.map(item => item.id === chapter.id ? { ...item, status: 'generating' } : item));

    try {
      await streamSectionContent(chapter, {
        signal: controller.signal,
        onChunk: (_content, accumulatedContent) => {
          if (batchCancelRequestedRef.current) {
            return;
          }
          const chars = accumulatedContent.replace(/\s+/g, '').length;
          updateBatchTask(chapter.id, {
            status: 'running',
            chars,
            percent: Math.min(98, Math.max(3, Math.round((chars / Math.max(targetWords, 1)) * 100))),
            message: '正在编写',
          });
          void syncBatchTaskItem(chapter.id, {
            status: 'running',
            chars,
            percent: Math.min(98, Math.max(3, Math.round((chars / Math.max(targetWords, 1)) * 100))),
            targetWords,
            message: '正在编写',
          });
        },
        onDone: () => {
          if (batchCancelRequestedRef.current) {
            updateBatchTask(chapter.id, {
              status: 'stopped',
              message: '已停止',
            });
            finalSyncs.push(syncBatchTaskItem(chapter.id, {
              status: 'stopped',
              message: '已停止',
            }));
            return;
          }
          updateBatchTask(chapter.id, {
            status: 'done',
            percent: 100,
            message: '已完成',
          });
          finalSyncs.push(syncBatchTaskItem(chapter.id, {
            status: 'done',
            percent: 100,
            targetWords,
            message: '已完成',
          }));
          setChapters(items => items.map(item => item.id === chapter.id ? { ...item, status: 'generated' } : item));
        },
      });
      if (finalSyncs.length) {
        await Promise.allSettled(finalSyncs);
      }
    } catch (error) {
      if (controller.signal.aborted || batchCancelRequestedRef.current) {
        updateBatchTask(chapter.id, {
          status: 'stopped',
          message: '已停止',
        });
        await syncBatchTaskItem(chapter.id, {
          status: 'stopped',
          message: '已停止',
        });
        return;
      }
      const errorMessage = error instanceof Error ? error.message : String(error);
      const preserveMessage = `${errorMessage}，已保留原正文`;
      updateBatchTask(chapter.id, {
        status: 'failed',
        percent: 100,
        message: preserveMessage,
      });
      await syncBatchTaskItem(chapter.id, {
        status: 'failed',
        percent: 100,
        targetWords,
        message: preserveMessage,
        error: errorMessage,
      });
      setChapters(items => items.map(item => item.id === chapter.id ? { ...item, status: 'failed', content: originalContent } : item));
    } finally {
      batchAbortControllersRef.current.delete(chapter.id);
    }
  }

  async function generateAllSectionsInBatch(): Promise<void> {
    if (!data?.project?.id || !chapters.length) {
      message.warning('当前没有可编写的章节');
      return;
    }
    if (sectionStreaming || batchGenerating) {
      message.warning('已有章节生成任务正在执行');
      return;
    }

    const sourceChapters = activeVolume === 'all' ? chapters : chapters.filter(chapter => matchesActiveVolume(chapter, activeVolume));
    const targets = sourceChapters.filter(needsBatchWriting);
    if (!targets.length) {
      setBatchTasks({});
      if (persistedBatchTask?.status === 'queued' || persistedBatchTask?.status === 'running') {
        setPersistedBatchTask(null);
        persistedBatchTaskIdRef.current = '';
      }
      message.info(`当前${volumeLabel(activeVolume)}章节都已生成，如需重写请点击单章重写正文`);
      return;
    }

    setMode('目录模式');
    setBatchGenerating(true);
    batchCancelRequestedRef.current = false;
    batchAbortControllersRef.current.clear();
    batchTaskSyncAtRef.current.clear();
    setDownloadUrl('');
    setBatchTasks(Object.fromEntries(targets.map(chapter => [chapter.id, {
      status: 'queued' as BatchTaskStatus,
      percent: 0,
      chars: 0,
      targetWords: targetChapterWords(chapter),
      message: '排队中',
    }])));

    let cursor = 0;
    try {
      const task = await createSectionGenerationTask(data.project.id, {
        volumeType: activeVolume,
        withImages,
        items: targets.map((chapter, index) => ({
          section_id: chapter.id,
          title: chapter.title,
          order_index: chapter.order_index || index + 1,
          volume_type: deliveryVolumeType(chapter),
          target_words: targetChapterWords(chapter),
        })),
      });
      setPersistedBatchTask({ id: task.id, status: task.status });
      persistedBatchTaskIdRef.current = task.id;
    } catch (error) {
      setBatchGenerating(false);
      const reason = error instanceof Error ? error.message : String(error);
      message.error(`创建批量生成任务失败：${reason}`);
      return;
    }

    async function worker(): Promise<void> {
      while (cursor < targets.length && !batchCancelRequestedRef.current) {
        const current = targets[cursor];
        cursor += 1;
        await generateSectionForBatch(current);
      }
    }

    try {
      await Promise.all(Array.from({ length: Math.min(BATCH_SECTION_CONCURRENCY, targets.length) }, () => worker()));
      if (batchCancelRequestedRef.current) {
        setBatchTasks(tasks => Object.fromEntries(Object.entries(tasks).map(([id, task]) => [
          id,
          task.status === 'queued' || task.status === 'running'
            ? { ...task, status: 'stopped' as BatchTaskStatus, message: '已停止' }
            : task,
        ])));
        if (data.project?.id && persistedBatchTaskIdRef.current) {
          void cancelSectionGenerationTask(data.project.id, persistedBatchTaskIdRef.current).then(task => {
            setPersistedBatchTask({ id: task.id, status: task.status });
            applyPersistedBatchTask(task);
          }).catch(error => {
            console.warn('取消批量章节生成任务同步失败', error);
          });
        }
        message.info('全文批量编写已停止');
      } else {
        if (data.project?.id) {
          void refreshLatestBatchTask(data.project.id);
        }
        message.success('全文批量编写任务已完成');
        setContentDirty(false);
        void refreshComplianceReport(data.project.id, { silent: true });
      }
    } finally {
      setBatchGenerating(false);
    }
  }

  function stopBatchGeneration(): void {
    if (!batchGenerating) {
      return;
    }
    batchCancelRequestedRef.current = true;
    batchAbortControllersRef.current.forEach(controller => controller.abort());
    setBatchTasks(tasks => Object.fromEntries(Object.entries(tasks).map(([id, task]) => [
      id,
      task.status === 'queued' || task.status === 'running'
        ? { ...task, status: 'stopped' as BatchTaskStatus, message: '已停止' }
        : task,
    ])));
    if (data?.project?.id && persistedBatchTaskIdRef.current) {
      void cancelSectionGenerationTask(data.project.id, persistedBatchTaskIdRef.current).then(task => {
        setPersistedBatchTask({ id: task.id, status: task.status });
        applyPersistedBatchTask(task);
      }).catch(error => {
        console.warn('取消批量章节生成任务同步失败', error);
      });
    }
  }

  function handleActiveVolumeChange(value: VolumeType): void {
    setActiveVolume(value);
    setSelectedId('');
    if (data?.project?.id) {
      void refreshComplianceReport(data.project.id, { silent: true, volumeType: value });
    }
  }

  if (loading) {
    return (
      <div className="bid-editor-loading">
        <div className="bid-editor-loading-panel">
          <BrandMark size={96} className="loading-brand" />
          <Alert type="info" showIcon message="正在加载标书编制工作台" description="正在读取当前项目的章节大纲。" />
        </div>
      </div>
    );
  }

  if (!outline && !streaming && !chapters.length) {
    return (
      <div className="bid-editor-empty">
        <Empty description="当前项目尚未生成章节大纲" />
        <Alert type="warning" showIcon message="请先回到招标解读页生成章节大纲，再进入标书编制。" />
      </div>
    );
  }

  if (mode === '目录模式') {
    return (
      <div className={`bid-editor-shell outline-mode-shell ${qualityCollapsed ? 'quality-collapsed' : ''}`}>
        <header className="bid-editor-topbar">
          <div className="bid-editor-brand">
            <FileText size={26} />
            <strong>{outline?.project_name || data?.project?.project_name || '测试标书'}</strong>
          </div>
          <Space size={10} wrap>
            <Button onClick={() => navigate('/interpretation')}>返回解读</Button>
            <Button icon={<BookOpen size={16} />}>关联资料</Button>
            <Button
              type="primary"
              icon={<Download size={17} />}
              loading={downloadGenerating === 'full'}
            disabled={!scopedChapters.length || !!downloadGenerating}
            onClick={() => void downloadDocx()}
          >
            {activeVolume === 'all' ? '标书下载' : `下载${volumeLabel(activeVolume)}`}
          </Button>
            {exportTask && downloadGenerating === 'full' ? (
              <Tooltip title={exportTask.message || '正在导出 DOCX'}>
                <Progress type="circle" size={34} percent={exportTask.progress || 0} />
              </Tooltip>
            ) : null}
          </Space>
        </header>

        <main className="outline-workbench">
          <section className="outline-topbar">
            <Segmented<EditorMode>
              value={mode}
              onChange={value => setMode(value)}
              options={[
                { label: '正文模式', value: '正文模式' },
                { label: '目录模式', value: '目录模式' },
              ]}
            />
            <Segmented<VolumeType>
              className="volume-segmented"
              value={activeVolume}
              onChange={handleActiveVolumeChange}
              options={volumeOptions.map(item => ({
                label: `${item.shortLabel} ${volumeCounts[item.value] || 0}`,
                value: item.value,
              }))}
            />
            <div className="outline-summary">
              <span>{volumeLabel(activeVolume)}章节：{scopedChapters.length}</span>
              <span>已生成章节：{generatedCount}</span>
              <span>用户目标：{lengthGoalPages} 页 / {lengthGoalChars.toLocaleString()} 字</span>
              <span>已生成：{currentEstimatedPages} 页 / {actualChars.toLocaleString()} 字</span>
              <span>章节计划：{estimatedTotalChars.toLocaleString()} 字（约{estimatedPages}页）</span>
              <span>篇幅进度：{lengthProgress}%</span>
              <span>进度：{generationProgress}%</span>
              {batchGenerating ? <span>批量并发：{BATCH_SECTION_CONCURRENCY} 路</span> : null}
            </div>
          </section>
          <section className="outline-panel">
            <div className="outline-panel-header">
              <div className="outline-panel-title">
                <BookOpen size={18} />
                <strong>标书目录</strong>
              </div>
              <Space size={10} wrap className="outline-toolbar-actions">
                <label className="outline-switch">
                  <input
                    type="checkbox"
                    checked={withImages}
                    onChange={event => setWithImages(event.target.checked)}
                  />
                  <span>全篇图文并茂</span>
                </label>
                <Tooltip title="设置目标页数、目标字数、技术标/商务标篇幅和生成策略">
                  <Button size="small" icon={<SlidersHorizontal size={14} />} onClick={openLengthSettings}>全文设置</Button>
                </Tooltip>
                <Button
                  size="small"
                  danger
                  icon={<RotateCcw size={14} />}
                  disabled={!chapters.length || batchGenerating || sectionStreaming}
                  onClick={() => {
                    setResetClearContent(false);
                    setResetModalOpen(true);
                  }}
                >
                  重置生成状态
                </Button>
                <Button size="small" icon={<Download size={14} />} onClick={downloadOutlineMarkdown}>下载目录</Button>
              </Space>
            </div>

            <div className="outline-table">
              {visibleChapters.map(chapter => {
                const wordMeta = chapterWordMeta(chapter);
                const plan = chapterWritingPlan(chapter);
                const task = visibleBatchTask(chapter);
                const active = chapter.id === selectedChapter?.id;
                return (
                  <div
                    key={`outline-${chapter.id}`}
                    className={`outline-row level-${chapter.level || 1} ${active ? 'active' : ''}`}
                    style={{ paddingLeft: `${20 + Math.max(0, (chapter.level || 1) - 1) * 28}px` }}
                  >
                    <button
                      type="button"
                      className="outline-row-toggle"
                      aria-label="展开或收起章节"
                      onClick={() => toggleChapter(chapter.id)}
                    >
                      {chapter.expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                    </button>
                    <button
                      type="button"
                      className="outline-row-title"
                      onClick={() => {
                        setSelectedId(chapter.id);
                      }}
                    >
                      <span>{chapterDisplayTitle(chapter)}</span>
                    </button>
                    <Tooltip title={wordMeta.tooltip}>
                      <div className={`outline-word-pill ${wordMeta.failed ? 'failed' : wordMeta.generated ? 'done' : 'pending'}`}>
                        {wordMeta.generated ? <CheckCircle2 size={13} /> : null}
                        <span>{wordMeta.label}</span>
                      </div>
                    </Tooltip>
                    <div className="outline-plan-tags">
                      <div className="outline-task-progress">
                        {task ? (
                          <>
                            <Tag color={batchStatusColor(task.status)}>{batchStatusLabel(task.status)}</Tag>
                            <Progress percent={task.percent} size="small" showInfo={false} status={task.status === 'failed' ? 'exception' : undefined} />
                          </>
                        ) : null}
                      </div>
                      <Tag color={plan.importance === 'high' ? 'red' : plan.importance === 'low' ? 'default' : 'blue'}>{chapterImportanceLabel(plan)}</Tag>
                      <Tag color="geekblue">建议 {plan.suggested_pages || '1-2'} 页</Tag>
                      {plan.needs_table ? <Tag color="cyan">需表格</Tag> : null}
                      {plan.needs_image ? <Tag color="purple">需图文</Tag> : null}
                      {plan.needs_qualification ? <Tag color="orange">需资质</Tag> : null}
                      {plan.needs_case ? <Tag color="green">需业绩</Tag> : null}
                    </div>
                    <div className="outline-row-actions">
                      <Button
                        type="link"
                        size="small"
                        icon={<Sparkles size={14} />}
                        loading={(sectionStreaming && selectedId === chapter.id) || task?.status === 'running'}
                        disabled={batchGenerating}
                        onClick={() => void generateCurrentSection(chapter)}
                      >
                        {wordMeta.generated ? '重写正文' : '生成正文'}
                      </Button>
                      <Button type="link" size="small" icon={<Eye size={14} />} onClick={() => previewChapter(chapter)}>预览</Button>
                      <Dropdown
                        trigger={['click']}
                        menu={{
                          items: outlineMoreMenuItems(chapter),
                          onClick: info => handleChapterMenu(info.key, chapter),
                        }}
                      >
                        <Button type="link" size="small" icon={<MoreVertical size={14} />}>更多</Button>
                      </Dropdown>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <footer className="outline-footer">
            <Space>
              <Button type="text" onClick={() => setAllExpanded(false)}>全部收起</Button>
              <Button type="text" onClick={() => setAllExpanded(true)}>全部展开</Button>
              {persistedBatchTask ? (
                <Tag color={persistedBatchTask.status === 'completed' ? 'success' : persistedBatchTask.status === 'failed' || persistedBatchTask.status === 'partial_failed' ? 'error' : 'processing'}>
                  任务已记录：{persistedBatchTask.status === 'completed' ? '已完成' : persistedBatchTask.status === 'cancelled' ? '已停止' : persistedBatchTask.status === 'partial_failed' ? '部分失败' : persistedBatchTask.status === 'failed' ? '失败' : '可恢复'}
                </Tag>
              ) : null}
            </Space>
            <Button
              type="primary"
              size="large"
              icon={<Sparkles size={18} />}
              loading={batchGenerating}
              disabled={!chapters.length || sectionStreaming}
              onClick={() => void generateAllSectionsInBatch()}
            >
              一键编写全文
            </Button>
            {batchGenerating ? (
              <Button
                danger
                size="large"
                icon={<Square size={16} />}
                onClick={stopBatchGeneration}
              >
                停止生成
              </Button>
            ) : null}
            <span />
          </footer>
        </main>
        <QualityDashboard />

        <Modal
          title="重置章节生成状态"
          open={resetModalOpen}
          okText={resetClearContent ? '重置并清空正文' : '仅重置状态'}
          cancelText="取消"
          okButtonProps={{ danger: resetClearContent, loading: resettingGeneration }}
          onOk={() => void resetGenerationStatus()}
          onCancel={() => setResetModalOpen(false)}
          destroyOnClose
        >
          <Alert
            type="warning"
            showIcon
            message="该操作会把全部章节恢复为未完成状态，用于重新测试或重新生成全文。"
            description={resetClearContent ? '当前已勾选清空正文，确认后所有章节正文会被清空。' : '默认只重置状态、进度和本地生成任务，保留已经生成的正文内容。'}
          />
          <label className="reset-content-option">
            <input
              type="checkbox"
              checked={resetClearContent}
              onChange={event => setResetClearContent(event.target.checked)}
            />
            <span>同时清空全部章节正文内容</span>
          </label>
        </Modal>
        <LengthSettingsModal />
        <ComplianceDrawer />
        <SemanticComplianceDrawer />
      </div>
    );
  }

  return (
    <div className={`bid-editor-shell ${qualityCollapsed ? 'quality-collapsed' : ''}`}>
      <header className="bid-editor-topbar">
        <div className="bid-editor-brand">
          <FileText size={26} />
          <strong>{outline?.project_name || data?.project?.project_name || '测试标书'}</strong>
        </div>
        <Space size={10} wrap>
          <Button onClick={() => navigate('/interpretation')}>返回解读</Button>
          <Button icon={<BookOpen size={16} />}>关联资料</Button>
          <Button
            type="primary"
            icon={<Download size={17} />}
            loading={downloadGenerating === 'full'}
            disabled={!scopedChapters.length || !!downloadGenerating}
            onClick={() => void downloadDocx()}
          >
            {activeVolume === 'all' ? '标书下载' : `下载${volumeLabel(activeVolume)}`}
          </Button>
          {exportTask && downloadGenerating === 'full' ? (
            <Tooltip title={exportTask.message || '正在导出 DOCX'}>
              <Progress type="circle" size={34} percent={exportTask.progress || 0} />
            </Tooltip>
          ) : null}
        </Space>
      </header>

      <aside className="bid-editor-sidebar">
        <div className="editor-mode-row">
          <Segmented<EditorMode>
            value={mode}
            onChange={value => setMode(value)}
            options={[
              { label: '正文模式', value: '正文模式' },
              { label: '目录模式', value: '目录模式' },
            ]}
          />
          <Button size="small" icon={<Plus size={15} />} onClick={() => void addChapter()}>新增章节</Button>
        </div>
        <Input
          allowClear
          size="small"
          prefix={<Search size={14} />}
          value={keyword}
          onChange={event => setKeyword(event.target.value)}
          suffix={<span className="match-count">{matchText}</span>}
          placeholder="输入章节名称搜索"
        />
        <Segmented<VolumeType>
          className="volume-segmented sidebar-volume-segmented"
          value={activeVolume}
          onChange={handleActiveVolumeChange}
          options={volumeOptions.map(item => ({
            label: `${item.shortLabel} ${volumeCounts[item.value] || 0}`,
            value: item.value,
          }))}
        />
        <div className={`chapter-tree ${streaming ? 'is-streaming' : ''}`}>
          {streaming ? (
            <div className="chapter-streaming-panel">
              <div className="chapter-streaming-head">
                <div className="stream-placeholder-icon chapter-streaming-icon">
                  <BrandMark size={34} rounded={false} />
                </div>
                <div>
                  <strong>AI 正在流式生成章节</strong>
                  <span>{streamText || '正在结合招标解读结果生成目录...'}</span>
                </div>
              </div>
            </div>
          ) : null}
          {visibleChapters.map(chapter => {
            const active = chapter.id === selectedChapter?.id;
            const childPlaceholder = (chapter.level || 1) === 1
              ? streamingChildPlaceholders.find(item => item.parentOrder === String(chapter.order || ''))
              : null;
            return (
              <Fragment key={chapter.id}>
                <div
                  className={`chapter-node level-${chapter.level || 1} ${active ? 'active' : ''}`}
                  style={{ paddingLeft: `${chapterIndent(chapter.level)}px` }}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedId(chapter.id)}
                  onKeyDown={event => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      setSelectedId(chapter.id);
                    }
                  }}
                >
                  <span className="chapter-toggle" onClick={event => { event.stopPropagation(); toggleChapter(chapter.id); }}>
                    {chapter.expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </span>
                  <Tooltip title={(() => {
                    const task = visibleBatchTask(chapter);
                    return task?.status ? batchStatusLabel(task.status) : isChapterGenerated(chapter) ? '已完成' : '未完成';
                  })()}>
                    <span className={`chapter-status ${chapterStatusClass(chapter)}`} />
                  </Tooltip>
                  <span className="chapter-title">{chapterDisplayTitle(chapter)}</span>
                  <Dropdown
                    trigger={['click']}
                    menu={{
                      items: chapterMenuItems(chapter),
                      onClick: info => {
                        info.domEvent.stopPropagation();
                        handleChapterMenu(info.key, chapter);
                      },
                    }}
                  >
                    <button
                      type="button"
                      className="chapter-more"
                      aria-label="章节操作"
                      onClick={event => event.stopPropagation()}
                    >
                      <MoreVertical size={15} />
                    </button>
                  </Dropdown>
                </div>
                {streaming && childPlaceholder && chapter.expanded ? (
                  <div
                    key={childPlaceholder.id}
                    className="chapter-node chapter-node-placeholder chapter-node-child-placeholder level-2"
                    style={{ paddingLeft: `${chapterIndent(2)}px` }}
                  >
                    <span className="chapter-toggle" />
                    <span className="chapter-status" />
                    <span className="chapter-title">{childPlaceholder.title}</span>
                  </div>
                ) : null}
              </Fragment>
            );
          })}
        </div>
        <footer className="chapter-stats">
          <span>总章节：{chapters.length}</span>
          <span>当前分册：{volumeLabel(activeVolume)}</span>
          <span>已完成字数：{actualChars}</span>
          <span>约{estimatedPages}页</span>
        </footer>
      </aside>

      <main className="bid-editor-main">
        <section className="editor-title-row">
          <div>
            <h1>{selectedChapter ? chapterDisplayTitle(selectedChapter) : '未选择章节'}</h1>
            <p>{streaming ? streamText : selectedChapter?.purpose || '使用 AI 编辑器编写章节正文，支持标题、列表、表格和 Markdown 存储。'}</p>
          </div>
          <Space>
            {streaming ? <Tag color="processing">大纲生成中</Tag> : null}
            {sectionStreaming ? <Tag color="processing">正文生成中</Tag> : null}
            {selectedChapter ? <Tag color="blue">{volumeLabel(deliveryVolumeType(selectedChapter))}</Tag> : null}
            {selectedChapter ? <Tag color="default">{internalVolumeLabel(inferVolumeType(selectedChapter))}</Tag> : null}
            <Button icon={<Save size={16} />} disabled={!selectedChapter || !contentDirty} onClick={() => void saveDraft()}>保存章节</Button>
            <Button icon={<Sparkles size={16} />} loading={sectionStreaming} disabled={!selectedChapter || streaming} onClick={() => void generateCurrentSection()}>生成本章正文</Button>
            <Button
              icon={<Download size={16} />}
              loading={downloadGenerating === 'section'}
              disabled={!selectedChapter || !!downloadGenerating}
              onClick={() => selectedChapter && void downloadDocx(selectedChapter.id)}
            >
              下载本章
            </Button>
            {exportTask && downloadGenerating === 'section' ? (
              <Tooltip title={exportTask.message || '正在导出 DOCX'}>
                <Progress type="circle" size={30} percent={exportTask.progress || 0} />
              </Tooltip>
            ) : null}
          </Space>
        </section>

        <section className="editor-workspace">
          {selectedChapter ? (
            <TiptapBidEditor
              content={selectedChapter.content || ''}
              onChange={handleEditorChange}
              placeholder="开始编写标书章节内容..."
            />
          ) : (
            <div className="editor-empty">
              <Empty description="请选择一个章节开始编辑" />
            </div>
          )}
        </section>

        <footer className="editor-statusbar">
          <span>当前章节：{selectedChapter ? chapterDisplayTitle(selectedChapter) : '-'}</span>
          <span>来源页码：{selectedChapter?.source_pages?.join('、') || '需复核'}</span>
          <span>Tiptap AI 编辑器</span>
        </footer>
      </main>
      <QualityDashboard />
      <ComplianceDrawer />
      <SemanticComplianceDrawer />
    </div>
  );
}
