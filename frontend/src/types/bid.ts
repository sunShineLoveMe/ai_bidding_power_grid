export interface UploadResponse {
  message: string;
  biddingId?: number | null;
  originalFilename: string;
  projectId?: string | null;
  fileId?: string | null;
  supabaseFileId?: string | null;
  supabaseSynced?: boolean;
  supabaseSyncError?: string | null;
}

export interface ParseStatusResponse {
  fileId: string;
  parseStatus?: string | null;
  parseCompleted?: boolean;
  failureStage?: string | null;
  errorType?: string | null;
  error?: string | null;
  userMessage?: string | null;
  retryable?: boolean;
  downloadRetryCount?: number;
  supabaseFile?: Record<string, unknown> | null;
  mineru?: Record<string, unknown>;
}

export interface GenerateBidDocumentResponse {
  message: string;
  markdown: string;
  editorConfig: Record<string, unknown>;
  fileUrl: string;
  downloadUrl: string;
}

export interface OnlyOfficeConfigResponse {
  message: string;
  markdown: string;
  editorConfig: Record<string, unknown>;
  fileUrl: string;
  downloadUrl: string;
}

export interface RecentTask {
  id: string;
  projectName: string;
  tenderUnit: string;
  createdAt: string;
  status: '待编辑' | '生成中' | '已导出' | '解析完成' | '已上传';
  action: '查看' | '继续' | '生成';
}
