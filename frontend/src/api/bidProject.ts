import { apiClient } from './client';
import type { GenerateBidDocumentResponse, OnlyOfficeConfigResponse, ParseStatusResponse, UploadResponse } from '../types/bid';
import type { BidLengthFeasibility, BidLengthSettings, BidSection, ComplianceReport, InterpretationResponse, SemanticComplianceReport } from '../types/interpretation';

export async function identifyUser(fingerprintId: string): Promise<{ userId: string | number; isNew: boolean; storage?: string }> {
  const response = await apiClient.post('/api/users/identify', { fingerprintId });
  return response.data;
}

export async function uploadTenderFile(file: File, userId: string | number): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('userId', String(userId));
  const response = await apiClient.post('/api/bidding/upload', form);
  return response.data;
}

export async function getParseStatus(fileId: string, options?: { projectId?: string | null; supabaseFileId?: string | null }): Promise<ParseStatusResponse> {
  const response = await apiClient.get(`/api/bidding/parse-status/${fileId}`, {
    params: {
      projectId: options?.projectId || undefined,
      supabaseFileId: options?.supabaseFileId || undefined,
    },
    skipGlobalLoading: true,
  });
  return response.data;
}

export async function retryHistoryParse(projectId: string): Promise<{
  message: string;
  projectId: string;
  fileId: string;
  supabaseFileId: string;
}> {
  const response = await apiClient.post(`/api/bidding/history/${projectId}/retry-parse`, undefined, {
    skipGlobalLoading: true,
  });
  return response.data;
}

export async function getLatestInterpretation(): Promise<InterpretationResponse> {
  const response = await apiClient.get('/api/bidding/interpretations/latest');
  return response.data;
}

export async function getInterpretation(projectId: string): Promise<InterpretationResponse> {
  const response = await apiClient.get(`/api/bidding/interpretations/${projectId}`);
  return response.data;
}

export async function getComplianceCheck(projectId: string, options?: { volumeType?: string }): Promise<ComplianceReport> {
  const response = await apiClient.get(`/api/bidding/interpretations/${projectId}/compliance-check`, {
    params: options?.volumeType ? { volumeType: options.volumeType } : undefined,
    skipGlobalLoading: true,
  });
  return response.data;
}

export async function runSemanticComplianceCheck(projectId: string, options?: {
  volumeType?: string;
  limit?: number;
  useLlm?: boolean;
}): Promise<SemanticComplianceReport> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/semantic-compliance-check`, {
    volumeType: options?.volumeType,
    limit: options?.limit || 12,
    useLlm: options?.useLlm ?? true,
  }, {
    skipGlobalLoading: true,
  });
  return response.data;
}

export async function generateComplianceSupplement(
  projectId: string,
  payload: { row: unknown; section: unknown },
): Promise<{ content: string; sectionId?: string; rowId?: string }> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/compliance-supplement`, payload, {
    skipGlobalLoading: true,
  });
  return response.data;
}

export async function generateAIInterpretation(projectId: string): Promise<unknown> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/ai-report`, undefined, {
    skipGlobalLoading: true,
    timeout: 360000,
  });
  return response.data;
}

export async function generateBidOutline(projectId: string): Promise<unknown> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/bid-outline`, undefined, {
    skipGlobalLoading: true,
    timeout: 360000,
  });
  return response.data;
}

export async function generateBidOutlineStream(projectId: string, onMessage?: (message: string) => void): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const source = new EventSource(`/api/bidding/interpretations/${projectId}/bid-outline/stream`);
    let settled = false;

    const closeAndReject = (error: Error): void => {
      if (settled) return;
      settled = true;
      source.close();
      reject(error);
    };

    source.addEventListener('start', event => {
      const payload = JSON.parse((event as MessageEvent).data) as { message?: string };
      if (payload.message) onMessage?.(payload.message);
    });
    source.addEventListener('meta', event => {
      const payload = JSON.parse((event as MessageEvent).data) as { total?: number; phase?: string };
      onMessage?.(payload.phase === 'quick'
        ? `已生成快速目录骨架，预计 ${payload.total || 0} 个章节，正在保存分册大纲。`
        : `AI 正在生成分册大纲，预计 ${payload.total || 0} 个章节。`);
    });
    source.addEventListener('stage', event => {
      const payload = JSON.parse((event as MessageEvent).data) as { message?: string };
      if (payload.message) onMessage?.(payload.message);
    });
    source.addEventListener('chapter', event => {
      const payload = JSON.parse((event as MessageEvent).data) as { index?: number; total?: number; chapter?: { title?: string } };
      onMessage?.(`正在生成章节 ${payload.index || 0} / ${payload.total || 0}：${payload.chapter?.title || '未命名章节'}`);
    });
    source.addEventListener('done', event => {
      if (settled) return;
      settled = true;
      source.close();
      resolve(JSON.parse((event as MessageEvent).data));
    });
    source.addEventListener('error', event => {
      const raw = (event as MessageEvent).data;
      if (raw) {
        try {
          const payload = JSON.parse(raw) as { error?: string };
          closeAndReject(new Error(payload.error || '分册大纲流式生成失败'));
          return;
        } catch {
          closeAndReject(new Error('分册大纲流式生成失败'));
          return;
        }
      }
      closeAndReject(new Error('分册大纲流式连接中断，请稍后重试。'));
    });
  });
}

export async function getBidSections(projectId: string): Promise<BidSection[]> {
  const response = await apiClient.get(`/api/bidding/interpretations/${projectId}/sections`);
  return response.data.sections || [];
}

export async function saveBidSection(projectId: string, section: Partial<BidSection>): Promise<BidSection> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/sections`, section, {
    skipGlobalLoading: true,
  });
  return response.data.section;
}

export async function saveBidLengthSettings(projectId: string, settings: BidLengthSettings): Promise<{
  settings: BidLengthSettings;
  feasibility: BidLengthFeasibility;
  allocations: Array<{ sectionId: string; targetWords: number }>;
  sections: BidSection[];
}> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/length-settings`, settings, {
    skipGlobalLoading: true,
  });
  return response.data;
}

export async function deleteBidSection(projectId: string, sectionId: string): Promise<void> {
  await apiClient.delete(`/api/bidding/interpretations/${projectId}/sections/${sectionId}`, {
    skipGlobalLoading: true,
  });
}

export async function reorderBidSections(projectId: string, sections: Partial<BidSection>[]): Promise<BidSection[]> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/sections/reorder`, { sections }, {
    skipGlobalLoading: true,
  });
  return response.data.sections || [];
}

export async function resetBidSectionsGeneration(projectId: string, clearContent = false): Promise<BidSection[]> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/sections/reset-generation`, { clearContent }, {
    skipGlobalLoading: true,
  });
  return response.data.sections || [];
}

export type SectionGenerationTaskItem = {
  section_id: string;
  title?: string;
  status: 'queued' | 'running' | 'done' | 'failed' | 'stopped';
  percent?: number;
  chars?: number;
  target_words?: number;
  message?: string;
  error?: string;
  saved_section_id?: string;
};

export type SectionGenerationTask = {
  id: string;
  project_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'partial_failed' | 'cancelled';
  volume_type: string;
  with_images: boolean;
  total_count: number;
  queued_count: number;
  running_count: number;
  done_count: number;
  failed_count: number;
  stopped_count: number;
  items: SectionGenerationTaskItem[];
  created_at?: string;
  updated_at?: string;
  finished_at?: string;
};

export async function getLatestSectionGenerationTask(projectId: string): Promise<SectionGenerationTask | null> {
  const response = await apiClient.get(`/api/bidding/interpretations/${projectId}/section-generation-tasks/latest`, {
    skipGlobalLoading: true,
  });
  return response.data.task || null;
}

export async function createSectionGenerationTask(
  projectId: string,
  payload: {
    volumeType: string;
    withImages: boolean;
    items: Array<{
      section_id: string;
      title?: string;
      order_index?: number;
      volume_type?: string;
      target_words?: number;
    }>;
  },
): Promise<SectionGenerationTask> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/section-generation-tasks`, payload, {
    skipGlobalLoading: true,
  });
  return response.data.task;
}

export async function updateSectionGenerationTaskItem(
  projectId: string,
  taskId: string,
  sectionId: string,
  patch: Partial<SectionGenerationTaskItem> & { task_status?: string },
): Promise<SectionGenerationTask> {
  const response = await apiClient.patch(
    `/api/bidding/interpretations/${projectId}/section-generation-tasks/${taskId}/items/${sectionId}`,
    patch,
    { skipGlobalLoading: true },
  );
  return response.data.task;
}

export async function cancelSectionGenerationTask(projectId: string, taskId: string): Promise<SectionGenerationTask> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/section-generation-tasks/${taskId}/cancel`, undefined, {
    skipGlobalLoading: true,
  });
  return response.data.task;
}

export type BidExportTask = {
  id: string;
  project_id: string;
  export_type: string;
  scope: 'full' | 'volume' | 'section';
  section_id?: string | null;
  volume_type?: string | null;
  with_images: boolean;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  message?: string;
  project_name?: string;
  file_name?: string;
  file_path?: string;
  download_url?: string;
  error_message?: string;
  metadata?: {
    image_selection?: {
      selected?: number;
      asset_candidates?: number;
      warnings?: string[];
      manifest?: Array<Record<string, unknown>>;
    };
    image_conversion?: {
      found?: number;
      inserted?: number;
      skipped?: number;
      failed?: number;
      events?: Array<Record<string, unknown>>;
    };
    [key: string]: unknown;
  };
  created_at?: string;
  updated_at?: string;
  finished_at?: string;
};

export async function generateOnlyOfficeConfig(projectId: string, sectionId?: string): Promise<OnlyOfficeConfigResponse> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/onlyoffice-config`, sectionId ? { sectionId } : undefined, {
    skipGlobalLoading: true,
    timeout: 180000,
  });
  return response.data;
}

export async function generateBidDocxDownload(
  projectId: string,
  options?: { sectionId?: string; withImages?: boolean; volumeType?: string; sectionsSnapshot?: Partial<BidSection>[] },
): Promise<{ task: BidExportTask; taskId: string }> {
  const response = await apiClient.post(`/api/bidding/interpretations/${projectId}/download-docx`, options || undefined, {
    skipGlobalLoading: true,
  });
  return response.data;
}

export async function getBidExportTask(projectId: string, taskId: string): Promise<BidExportTask> {
  const response = await apiClient.get(`/api/bidding/interpretations/${projectId}/export-tasks/${taskId}`, {
    skipGlobalLoading: true,
  });
  return response.data.task;
}

export async function preAnalyzeBid(biddingId: number): Promise<unknown> {
  const response = await apiClient.post('/api/bidding/pre-analysis_bid', { biddingId });
  return response.data;
}

export async function analyzeChapters(biddingId: number): Promise<unknown> {
  const response = await apiClient.post('/api/bidding/chapter-analysis_bid', { biddingId });
  return response.data;
}

export async function designChapters(biddingId: number): Promise<unknown> {
  const response = await apiClient.post('/api/bidding/chapter-design', { biddingId });
  return response.data;
}

export async function generateBidDocument(
  biddingId: number,
  chapterDesign: unknown,
): Promise<GenerateBidDocumentResponse> {
  const response = await apiClient.post('/api/bidding/generate-bid-document', {
    biddingId,
    chapterDesign,
  });
  return response.data;
}

/**
 * 批量获取知识资产的 Supabase Storage 签名 URL。
 * 前端拿到签名 URL 后直接请求 Supabase CDN，无需经过后端中转。
 * 有效期默认 1 小时（3600 秒）。
 */
export async function getKnowledgeAssetSignedUrls(
  assetIds: string[],
  expiresIn = 3600,
): Promise<Record<string, string>> {
  if (!assetIds.length) return {};
  const response = await apiClient.post(
    '/api/knowledge/assets/signed-urls',
    { assetIds, expiresIn },
    { skipGlobalLoading: true },
  );
  return (response.data as { urls: Record<string, string> }).urls || {};
}
