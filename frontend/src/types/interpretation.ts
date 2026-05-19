export interface BidProject {
  id: string;
  project_name?: string | null;
  project_no?: string | null;
  tender_unit?: string | null;
  agency?: string | null;
  project_type?: string | null;
  status?: string | null;
  created_at?: string | null;
}

export interface BidAnalysis {
  id: string;
  project_id: string;
  project_meta?: Record<string, unknown> | null;
  qualification_requirements?: unknown[] | null;
  document_checklist?: unknown[] | null;
  scoring_items?: unknown[] | null;
  risk_items?: unknown[] | null;
  chapter_suggestions?: unknown[] | null;
  summary?: string | null;
}

export interface InterpretationReport {
  title?: string;
  executive_summary?: string[];
  qualification_focus?: string[];
  business_focus?: string[];
  technical_focus?: string[];
  scoring_strategy?: string[];
  risk_focus?: string[];
  chapter_plan?: string[];
  next_actions?: string[];
}

export interface BidOutlineChapter {
  id?: string;
  parent_id?: string | null;
  order?: number | string;
  order_index?: number;
  level?: number;
  title?: string;
  status?: string;
  priority?: 'high' | 'medium' | 'low' | string;
  purpose?: string;
  response_points?: string[];
  mapped_requirements?: string[];
  mapped_scoring_items?: string[];
  mapped_risks?: string[];
  source_pages?: number[];
  required_materials?: string[];
  writing_notes?: string[];
  content?: string;
  metadata?: Record<string, unknown> & {
    volume_type?: string;
    volume_name?: string;
    export_group?: string;
    document_role?: string;
  };
}

export interface BidOutlineVolume {
  type?: 'qualification' | 'business' | 'technical' | 'price' | 'attachment' | 'other' | string;
  name?: string;
  required?: boolean;
  basis?: string;
  chapters?: BidOutlineChapter[];
}

export interface ChapterWritingPlan {
  importance?: 'high' | 'medium' | 'low' | string;
  min_words?: number;
  max_words?: number;
  target_words?: number;
  suggested_pages?: string;
  needs_table?: boolean;
  needs_image?: boolean;
  needs_qualification?: boolean;
  needs_case?: boolean;
  generation_mode?: 'single_pass' | 'multi_pass' | string;
  strategy?: string;
  length_settings_source?: string;
  allow_auto_expand?: boolean;
}

export interface BidLengthSettings {
  mode: 'pages' | 'words';
  technicalPages: number;
  businessPages: number;
  technicalWords: number;
  businessWords: number;
  allowAutoExpand?: boolean;
}

export interface BidLengthFeasibility {
  level: 'ok' | 'warning' | string;
  recommendedTechnicalPages?: number;
  recommendedBusinessPages?: number;
  warnings?: string[];
}

export interface BidSection extends BidOutlineChapter {
  id: string;
  project_id: string;
  parent_id?: string | null;
  order_index: number;
  level: number;
  title: string;
  status: string;
  content: string;
  created_at?: string;
  updated_at?: string;
}

export interface BidOutline {
  version?: string;
  generated_at?: string;
  model?: string;
  project_name?: string;
  tender_no?: string;
  summary?: string;
  volumes?: BidOutlineVolume[];
  chapters?: BidOutlineChapter[];
  next_steps?: string[];
}

export interface AIInterpretationReport {
  executive_summary?: string[];
  project_brief?: {
    project_name?: string;
    tender_no?: string;
    procurement_scope?: string;
    key_deadlines?: string[];
    core_conclusion?: string;
  };
  qualification_review?: Array<{
    requirement?: string;
    judgement?: string;
    evidence?: string;
    source_page?: number | null;
    action?: string;
  }>;
  scoring_strategy?: Array<{
    scoring_point?: string;
    score?: number | null;
    strategy?: string;
    supporting_materials?: string[];
    source_page?: number | null;
    evidence?: string;
  }>;
  risk_warnings?: Array<{
    risk_level?: string;
    risk?: string;
    impact?: string;
    source_page?: number | null;
    evidence?: string;
    mitigation?: string;
  }>;
  document_plan?: Array<{
    chapter?: string;
    purpose?: string;
    key_points?: string[];
    related_requirements?: string[];
  }>;
  material_checklist?: Array<{
    material?: string;
    category?: string;
    required?: boolean;
    owner?: string;
    note?: string;
  }>;
  next_actions?: string[];
}

export interface MinerUQuality {
  quality_score?: number;
  markdown_chars?: number;
  content_blocks?: number;
  page_count?: number;
  block_type_counts?: Record<string, number>;
  avg_text_block_length?: number;
  pages?: Array<{ page: number; blocks: number }>;
  missing_pages?: number[];
  suspicious_blocks?: Array<{ type?: string; page?: number | null; reason?: string; text?: string }>;
  checklist?: Array<{ label: string; ok: boolean }>;
  artifacts?: Record<string, string | null>;
}

export interface RequirementItem {
  id: string;
  requirement_type?: string | null;
  title?: string | null;
  content?: string | null;
  priority?: string | null;
  source_section?: string | null;
  source_page?: number | null;
  source_text?: string | null;
}

export interface RiskItem {
  id: string;
  risk_level?: string | null;
  risk_type?: string | null;
  content?: string | null;
  action?: string | null;
  source_section?: string | null;
  source_page?: number | null;
  source_text?: string | null;
}

export interface ScoringItem {
  id: string;
  category?: string | null;
  item?: string | null;
  score?: number | null;
  requirement?: string | null;
  response_suggestion?: string | null;
  target_chapter?: string | null;
  source_section?: string | null;
  source_page?: number | null;
  source_text?: string | null;
}

export interface ChapterSuggestion {
  id: string;
  chapter_title?: string | null;
  reason?: string | null;
  priority?: string | null;
}

export interface ComplianceRow {
  id: string;
  category: '要求条款' | '评分项' | '风险项' | string;
  importance: string;
  content: string;
  status: 'covered' | 'partial' | 'missing';
  matchedChapter?: string | null;
  matchedChapterId?: string | null;
  suggestedChapter?: string | null;
  suggestedChapterId?: string | null;
  sourcePage?: number | null;
  sourceText?: string | null;
  volumeType?: string;
  volumeName?: string;
  deliveryVolumeType?: string;
  deliveryVolumeName?: string;
}

export interface ComplianceVolumeSummary {
  volumeType: string;
  volumeName: string;
  total: number;
  covered: number;
  partial: number;
  missing: number;
  percent: number;
  highRiskMissing?: number;
}

export interface ComplianceReport {
  projectId: string;
  projectName?: string | null;
  summary: {
    metricName?: string;
    scopeNote?: string;
    volumeType?: string;
    volumeName?: string;
    total: number;
    covered: number;
    partial: number;
    missing: number;
    percent: number;
    highRiskMissing?: number;
  };
  volumeSummaries?: ComplianceVolumeSummary[];
  rows: ComplianceRow[];
  recommendations: string[];
}

export interface SemanticComplianceReview {
  rowId: string;
  category: string;
  importance?: string;
  status: 'covered' | 'partial' | 'missing';
  evidence: string;
  confidence: number;
  weight: string;
  suggestion: string;
  targetSectionId?: string | null;
  targetSectionTitle?: string | null;
  llmReviewed?: boolean;
}

export interface SemanticComplianceReport {
  projectId: string;
  volumeType: string;
  volumeName: string;
  baseSummary?: ComplianceReport['summary'];
  summary: {
    total: number;
    covered: number;
    partial: number;
    missing: number;
    percent: number;
    llmReviewed?: number;
  };
  reviews: SemanticComplianceReview[];
  recommendations: string[];
}

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  content: string;
  source_page?: number | null;
  source_section?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface InterpretationResponse {
  project: BidProject | null;
  analysis: BidAnalysis | null;
  requirements: RequirementItem[];
  risks: RiskItem[];
  scoringItems: ScoringItem[];
  chapterSuggestions: ChapterSuggestion[];
  documentChunks: DocumentChunk[];
  sections?: BidSection[];
}
