import { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Progress, Steps, Tag, Upload, message } from 'antd';
import type { UploadProps } from 'antd';
import { CheckCircle2, FileSearch, FileUp, RotateCcw, SquarePen } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  generateAIInterpretation,
  generateBidOutlineStream,
  getParseStatus,
  identifyUser,
  uploadTenderFile,
} from '../../api/bidProject';
import { BrandMark } from '../common/BrandMark';
import { useBidProjectStore } from '../../stores/bidProjectStore';

type StepStatus = 'wait' | 'process' | 'finish' | 'error';
const ACTIVE_WORKFLOW_KEY = 'aiBiddingActiveWorkflow';

interface ActiveWorkflow {
  fileName: string;
  fileId: string;
  projectId: string;
  supabaseFileId?: string | null;
  startedAt: number;
}

interface BidWorkflowProps {
  onReady?: (openFilePicker: () => void) => void;
  onTaskChanged?: () => void;
}

const workflowSteps = [
  {
    title: '上传招标文件',
    description: '创建投标任务',
  },
  {
    title: '解析招标文件',
    description: '文本 / 表格 / OCR',
  },
  {
    title: '生成招标解读',
    description: '资格 / 评分 / 风险',
  },
  {
    title: '生成分册大纲',
    description: '技术 / 商务 / 资格 / 报价',
  },
  {
    title: '进入标书编制',
    description: '编辑并导出 Word',
  },
] as const;

function delay(ms: number): Promise<void> {
  return new Promise(resolve => {
    window.setTimeout(resolve, ms);
  });
}

function initialStatuses(): StepStatus[] {
  return workflowSteps.map(() => 'wait');
}

function readActiveWorkflow(): ActiveWorkflow | null {
  try {
    const raw = localStorage.getItem(ACTIVE_WORKFLOW_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ActiveWorkflow;
    if (!parsed.fileId || !parsed.projectId) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveActiveWorkflow(task: ActiveWorkflow): void {
  localStorage.setItem(ACTIVE_WORKFLOW_KEY, JSON.stringify(task));
}

function clearActiveWorkflow(): void {
  localStorage.removeItem(ACTIVE_WORKFLOW_KEY);
}

export function BidWorkflow({ onReady, onTaskChanged }: BidWorkflowProps): JSX.Element {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const runTokenRef = useRef(0);
  const activeStepRef = useRef(0);
  const [file, setFile] = useState<File | null>(null);
  const [userId, setUserId] = useState<string | number | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [current, setCurrent] = useState(0);
  const [statuses, setStatuses] = useState<StepStatus[]>(initialStatuses);
  const [summary, setSummary] = useState('请选择招标文件。上传后系统会自动完成解析、招标解读和分册大纲生成。');
  const [detail, setDetail] = useState('支持 Word、PDF、TXT。扫描版 PDF 会自动进入 MinerU/OCR 解析流程。');
  const addTask = useBidProjectStore(state => state.addTask);

  const openFilePicker = useCallback(() => inputRef.current?.click(), []);

  useEffect(() => {
    onReady?.(openFilePicker);
  }, [onReady, openFilePicker]);

  useEffect(() => {
    const active = readActiveWorkflow();
    if (!active || busy) return;
    void resumeWorkflow(active);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function getUserId(): Promise<string | number> {
    if (userId) return userId;
    const fingerprintId = localStorage.getItem('enshiBiddingFingerprint') || `enshi-bidding-${Date.now()}`;
    localStorage.setItem('enshiBiddingFingerprint', fingerprintId);
    const data = await identifyUser(fingerprintId);
    setUserId(data.userId);
    return data.userId;
  }

  function updateStep(index: number, status: StepStatus, nextSummary?: string, nextDetail?: string): void {
    activeStepRef.current = index;
    setCurrent(index);
    setStatuses(prev => prev.map((item, itemIndex) => (itemIndex === index ? status : item)));
    if (nextSummary) setSummary(nextSummary);
    if (nextDetail) setDetail(nextDetail);
  }

  function finishStep(index: number): void {
    setStatuses(prev => prev.map((item, itemIndex) => (itemIndex === index ? 'finish' : item)));
  }

  async function waitForParseIndexed(fileId: string, token: number, options?: { projectId?: string | null; supabaseFileId?: string | null }): Promise<void> {
    for (let count = 1; count <= 90; count += 1) {
      if (runTokenRef.current !== token) return;
      const data = await getParseStatus(fileId, options);
      const parseStatus = data.parseStatus || 'pending';
      const mineru = (data.mineru || {}) as Record<string, unknown>;
      const splitDetail = mineru.split && mineru.part_count
        ? `当前为超 200 页 PDF，已自动分为 ${mineru.part_count} 份解析${mineru.current_part ? `，正在处理第 ${mineru.current_part} 份（${mineru.current_part_pages || ''} 页）` : ''}。`
        : '';
      const retryDetail = data.downloadRetryCount ? `结果下载已重试 ${data.downloadRetryCount} 次。` : '';
      const userHint = data.userMessage ? `${data.userMessage}。` : '';
      setDetail(`解析状态：${parseStatus}。${splitDetail}${retryDetail}${userHint}系统正在抽取文本、表格和图片信息，第 ${count} 次检查。`);

      if (data.parseCompleted || parseStatus === 'indexed') {
        setDetail(`解析状态：${parseStatus}。招标文件解析结果已完成落库，正在进入招标解读。`);
        return;
      }
      if ([
        'mineru_failed',
        'index_failed',
        'ocr_required',
        'mineru_download_failed',
        'mineru_import_failed',
        'supabase_sync_failed',
      ].includes(parseStatus)) {
        const errorDetail = String(data.userMessage || mineru.user_message || mineru.error || mineru.reason || data.error || '');
        throw new Error(errorDetail || '招标文件解析失败，请检查文件是否可读，或在历史记录中重试 MinerU/OCR 解析。');
      }
      await delay(5000);
    }
    throw new Error('招标文件解析等待超时，请到招标解读页查看后台解析状态。');
  }

  async function runWorkflow(selectedFile: File): Promise<void> {
    if (busy) {
      message.info('当前任务正在处理中，请等待完成后再上传新文件。');
      return;
    }

    const token = runTokenRef.current + 1;
    runTokenRef.current = token;
    setFile(selectedFile);
    setProjectId(null);
    setBusy(true);
    setCurrent(0);
    activeStepRef.current = 0;
    setStatuses(initialStatuses());
    setSummary('正在上传招标文件...');
    setDetail(`已选择：${selectedFile.name}`);

    try {
      updateStep(0, 'process', '正在上传招标文件...', '系统正在创建项目任务并同步文件到知识库。');
      const resolvedUserId = await getUserId();
      const uploadResult = await uploadTenderFile(selectedFile, resolvedUserId);
      if (runTokenRef.current !== token) return;

      addTask({
        projectName: selectedFile.name.replace(/\.[^.]+$/, ''),
        tenderUnit: '本地上传',
        status: '已上传',
        action: '查看',
      });
      onTaskChanged?.();
      finishStep(0);

      if (!uploadResult.projectId) {
        throw new Error('上传成功，但未返回项目 ID，无法继续自动生成招标解读。');
      }
      setProjectId(uploadResult.projectId);
      if (uploadResult.fileId) {
        saveActiveWorkflow({
          fileName: selectedFile.name,
          fileId: uploadResult.fileId,
          projectId: uploadResult.projectId,
          supabaseFileId: uploadResult.supabaseFileId,
          startedAt: Date.now(),
        });
      }

      updateStep(1, 'process', '正在解析招标文件...', '系统正在识别正文、表格、图片和扫描页，完成后会自动进入招标解读。');
      if (uploadResult.fileId) {
        await waitForParseIndexed(uploadResult.fileId, token, {
          projectId: uploadResult.projectId,
          supabaseFileId: uploadResult.supabaseFileId,
        });
      }
      if (runTokenRef.current !== token) return;
      finishStep(1);

      updateStep(2, 'process', '正在生成招标解读...', '正在提取项目概况、资格要求、评分标准、废标风险和关键时间节点。');
      await generateAIInterpretation(uploadResult.projectId);
      if (runTokenRef.current !== token) return;
      finishStep(2);

      updateStep(3, 'process', '正在生成分册大纲...', '正在结合招标解读、企业知识库、资信库和产品库规划技术标、商务标、资格文件和报价文件。');
      await generateBidOutlineStream(uploadResult.projectId, text => {
        if (runTokenRef.current === token) setDetail(text);
      });
      if (runTokenRef.current !== token) return;
      finishStep(3);

      updateStep(4, 'finish', '分册大纲已生成，可以进入标书编制。', '后续可在标书编制工作台中按分册编辑正文、引用资料并导出 Word。');
      clearActiveWorkflow();
      message.success('招标解读和分册大纲已生成');
      onTaskChanged?.();
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      setCurrent(activeStepRef.current);
      setStatuses(prev => prev.map((item, index) => (index === activeStepRef.current ? 'error' : item)));
      setSummary('自动流程执行失败');
      setDetail(reason);
      message.error(reason);
    } finally {
      setBusy(false);
    }
  }

  async function resumeWorkflow(active: ActiveWorkflow): Promise<void> {
    const token = runTokenRef.current + 1;
    runTokenRef.current = token;
    setFile(null);
    setProjectId(active.projectId);
    setBusy(true);
    setCurrent(1);
    activeStepRef.current = 1;
    setStatuses(['finish', 'process', 'wait', 'wait', 'wait']);
    setSummary('正在恢复未完成的招标文件流程...');
    setDetail(`检测到未完成任务：${active.fileName}。系统将继续解析、解读和生成分册大纲。`);

    try {
      // 先检查项目当前状态：
      //   1. 如果项目已被删除（project === null），直接清 localStorage 并退出
      //   2. 如果已有 analysis/sections，跳过对应步骤
      //   3. 否则按未完成处理
      let projectExists = false;
      let hasInterpretation = false;
      let hasOutline = false;
      let probeSucceeded = false;

      try {
        const { getInterpretation } = await import('../../api/bidProject');
        const interp = await getInterpretation(active.projectId);
        probeSucceeded = true;
        projectExists = !!(interp?.project);
        hasInterpretation = !!(interp?.analysis);
        hasOutline = !!(interp?.sections && interp.sections.length > 0);
      } catch {
        // 查询失败（网络抖动/服务异常），按未完成处理但仍尝试恢复
        probeSucceeded = false;
      }

      // 项目已被删除：不再恢复流程，清除 localStorage，重置 UI
      if (probeSucceeded && !projectExists) {
        clearActiveWorkflow();
        setStatuses(initialStatuses());
        setCurrent(0);
        setProjectId(null);
        setSummary('请选择招标文件。上传后系统会自动完成解析、招标解读和分册大纲生成。');
        setDetail('检测到之前的未完成任务对应的项目已被删除，已清除本地恢复标记。');
        setBusy(false);
        return;
      }

      // 项目已完全完成：直接显示完成状态
      if (hasInterpretation && hasOutline) {
        finishStep(1);
        finishStep(2);
        finishStep(3);
        updateStep(4, 'finish', '检测到已完成的标书项目，可直接进入编制。', '点击右侧「进入标书编制」继续完善内容并导出 Word。');
        clearActiveWorkflow();
        onTaskChanged?.();
        setBusy(false);
        return;
      }

      // 按需补跑未完成的步骤
      const parseCompleted = hasInterpretation;  // 有解读说明解析也已完成

      if (!parseCompleted) {
        updateStep(1, 'process', '正在恢复解析进度...', '正在从后台查询 MinerU/OCR 解析状态。');
        await waitForParseIndexed(active.fileId, token, {
          projectId: active.projectId,
          supabaseFileId: active.supabaseFileId,
        });
        if (runTokenRef.current !== token) return;
      }
      finishStep(1);

      if (!hasInterpretation) {
        updateStep(2, 'process', '正在生成招标解读...', '解析已完成，继续提取项目概况、资格要求、评分标准和风险项。');
        await generateAIInterpretation(active.projectId);
        if (runTokenRef.current !== token) return;
      }
      finishStep(2);

      if (!hasOutline) {
        updateStep(3, 'process', '正在生成分册大纲...', '正在结合招标解读和知识库规划技术标、商务标、资格文件和报价文件。');
        await generateBidOutlineStream(active.projectId, text => {
          if (runTokenRef.current === token) setDetail(text);
        });
        if (runTokenRef.current !== token) return;
      }
      finishStep(3);

      updateStep(4, 'finish', '分册大纲已生成，可以进入标书编制。', '后续可继续按分册编辑章节正文并导出 Word。');
      clearActiveWorkflow();
      onTaskChanged?.();
      message.success('已恢复并完成招标解读和分册大纲生成');
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      // 如果是"项目不存在"或"分析数据不存在"类错误，说明 localStorage 数据已失效
      const isStaleError = /不存在|not found|尚无结构化解读/.test(reason);
      if (isStaleError) {
        clearActiveWorkflow();
        setStatuses(initialStatuses());
        setCurrent(0);
        setProjectId(null);
        setSummary('请选择招标文件。上传后系统会自动完成解析、招标解读和分册大纲生成。');
        setDetail('之前的未完成任务已失效（项目可能已被删除），已清除本地恢复标记。');
      } else {
        setCurrent(activeStepRef.current);
        setStatuses(prev => prev.map((item, index) => (index === activeStepRef.current ? 'error' : item)));
        setSummary('恢复流程失败');
        setDetail(reason);
        message.error(reason);
      }
    } finally {
      if (runTokenRef.current === token) {
        setBusy(false);
      }
    }
  }

  const uploadProps: UploadProps = {
    showUploadList: false,
    disabled: busy,
    beforeUpload: selectedFile => {
      void runWorkflow(selectedFile);
      return false;
    },
  };

  const completedCount = statuses.filter(status => status === 'finish').length;
  const progressPercent = Math.round((completedCount / workflowSteps.length) * 100);
  const outlineReady = statuses[3] === 'finish' || progressPercent === 100;
  const interpretationLabel = current <= 1
    ? '查看解析结果'
    : busy && current === 2
      ? '查看生成中的解读'
      : '查看招标解读';
  const interpretationDisabled = !projectId;
  const editorDisabled = !projectId || !outlineReady;

  return (
    <section className="panel-card">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="panel-title mb-1">标书生成流程</h2>
          <p className="m-0 text-sm font-semibold text-slate-500">
            上传一次招标文件，系统自动完成解析、解读和分册大纲生成，减少重复点击。
          </p>
        </div>
        <Tag color={busy ? 'processing' : progressPercent === 100 ? 'success' : 'default'}>
          {busy ? '自动执行中' : progressPercent === 100 ? '已完成' : '等待上传'}
        </Tag>
      </div>

      <Upload.Dragger {...uploadProps} className="compact-uploader">
        <div className="flex h-24 flex-col items-center justify-center gap-2">
          <FileUp className="text-blue-500" size={26} />
          <strong className="text-blue-600">{file ? file.name : '选择或拖拽招标文件'}</strong>
          <span className="text-xs font-semibold text-slate-500">支持 Word、PDF、TXT；上传后自动执行后续流程</span>
        </div>
      </Upload.Dragger>
      <input
        ref={inputRef}
        hidden
        type="file"
        accept=".doc,.docx,.pdf,.txt"
        onChange={event => {
          const selectedFile = event.target.files?.[0];
          if (selectedFile) {
            void runWorkflow(selectedFile);
          }
          event.target.value = '';
        }}
      />

      <div className="mt-5 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-5">
        <Steps
          size="small"
          current={current}
          status={statuses[current] === 'error' ? 'error' : busy ? 'process' : 'wait'}
          items={workflowSteps.map((step, index) => ({
            title: step.title,
            description: step.description,
            status: statuses[index],
          }))}
        />
      </div>

      <div className="mt-4 grid grid-cols-[1fr_260px] gap-4 max-[1500px]:grid-cols-1">
        <div className="rounded-2xl border border-slate-100 bg-white px-5 py-4">
          <div className="mb-3 flex items-center gap-3">
            {busy ? (
              <BrandMark size={28} className="brand-loading-logo brand-loading-logo-sm" />
            ) : progressPercent === 100 ? (
              <CheckCircle2 className="text-emerald-500" size={22} />
            ) : (
              <FileSearch className="text-blue-600" size={22} />
            )}
            <div>
              <h3 className="m-0 text-base font-black text-slate-950">{summary}</h3>
              <p className="m-0 mt-1 text-sm font-semibold leading-6 text-slate-500">{detail}</p>
            </div>
          </div>
          <Progress percent={progressPercent} showInfo={false} strokeColor="#3267ff" />
        </div>

        <div className="flex flex-col justify-center gap-3 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-4">
          <Button
            type={editorDisabled ? 'default' : 'primary'}
            icon={<SquarePen size={16} />}
            disabled={editorDisabled}
            onClick={() => {
              if (projectId) window.location.href = `/bid-editor?projectId=${projectId}`;
            }}
          >
            进入标书编制
          </Button>
          <Button
            type={!editorDisabled ? 'default' : 'primary'}
            disabled={interpretationDisabled}
            onClick={() => {
              if (projectId) navigate(`/interpretation?projectId=${projectId}`);
            }}
          >
            {interpretationLabel}
          </Button>
          <Button
            icon={<RotateCcw size={16} />}
            disabled={!file || busy}
            onClick={() => {
              if (file) void runWorkflow(file);
            }}
          >
            重新执行流程
          </Button>
        </div>
      </div>
    </section>
  );
}
