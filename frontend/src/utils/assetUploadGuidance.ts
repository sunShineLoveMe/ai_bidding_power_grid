export type AssetLibraryType = 'product' | 'qualification';

export type AssetQualityTier = 'formal_bid_ready' | 'knowledge_only' | 'review_only' | 'restricted';

export interface AssetEvidenceOption {
  label: string;
  value: string;
  library: AssetLibraryType;
  recommendedFormats: string;
  guidance: string;
  warning?: string;
}

export interface UploadQualityPreview {
  tier: AssetQualityTier;
  label: string;
  color: string;
  notes: string[];
  width?: number;
  height?: number;
}

export const productEvidenceOptions: AssetEvidenceOption[] = [
  {
    label: '产品实物图片',
    value: 'product_image',
    library: 'product',
    recommendedFormats: '原始高清 JPG/PNG/WebP',
    guidance: '上传产品实物、型号、包装或成品展示图，适合技术响应和产品介绍章节。',
  },
  {
    label: '生产制造能力',
    value: 'production_capacity',
    library: 'product',
    recommendedFormats: '原始高清照片、完整 PDF、DOCX',
    guidance: '上传生产线、车间、厂房、仓储等实景资料。建议使用原图或完整页，不要上传微信截图和局部裁剪图。',
  },
  {
    label: '试验检测设备',
    value: 'testing_capacity',
    library: 'product',
    recommendedFormats: '原始高清照片、设备清单 PDF/DOCX',
    guidance: '上传检测设备、试验设备、计量器具等资料。局部设备铭牌或单个编号截图需要人工复核。',
  },
  {
    label: '检验报告',
    value: 'inspection_report',
    library: 'product',
    recommendedFormats: '完整 PDF 或整页扫描件',
    guidance: '建议上传完整检验报告 PDF 或整页扫描件，系统可用于检索和参数佐证。不要只上传二维码、印章或局部参数截图。',
  },
  {
    label: '绿色低碳资料',
    value: 'green_low_carbon',
    library: 'product',
    recommendedFormats: '完整 PDF、证书扫描件、报告 DOCX',
    guidance: '上传绿色供应链、碳足迹、环保检测、节能低碳等资料，需保证来源为企业事实资料。',
  },
  {
    label: '厂房仓储资料',
    value: 'warehouse_capacity',
    library: 'product',
    recommendedFormats: '原始高清照片、完整 PDF',
    guidance: '上传厂房、仓库、库区、备货能力等实景资料，优先使用横向或整页清晰图片。',
  },
  {
    label: '产品参数表',
    value: 'product_parameter_table',
    library: 'product',
    recommendedFormats: '原始 XLS/XLSX/CSV',
    guidance: '上传原始 Excel 或 CSV，系统后续可结构化抽取型号、参数、保证值。不要把表格截图当作参数表上传。',
    warning: '表格资料默认仅用于知识库和结构化抽取，不自动作为正式标书配图。',
  },
  {
    label: '技术响应资料',
    value: 'technical_response',
    library: 'product',
    recommendedFormats: 'DOCX、PDF、XLSX',
    guidance: '上传技术响应、偏差表、参数承诺等资料，优先保留可编辑文件。',
  },
];

export const qualificationEvidenceOptions: AssetEvidenceOption[] = [
  {
    label: '基础证照',
    value: 'business_license',
    library: 'qualification',
    recommendedFormats: '完整 PDF 或整页扫描件',
    guidance: '上传营业执照、开户许可等完整证照。不要上传局部二维码、印章或只截取证号区域。',
  },
  {
    label: '资质证书',
    value: 'certification',
    library: 'qualification',
    recommendedFormats: '完整 PDF 或整页扫描件',
    guidance: '上传体系认证、产品认证、许可资质等完整证书，证书编号和有效期应可追溯。',
  },
  {
    label: '财务资料',
    value: 'finance',
    library: 'qualification',
    recommendedFormats: '完整 PDF、审计报告 DOCX/PDF',
    guidance: '上传审计报告、银行资信、财务报表等完整资料。敏感财务资料建议上传前确认脱敏策略。',
  },
  {
    label: '人员证书',
    value: 'personnel_certificate',
    library: 'qualification',
    recommendedFormats: '完整 PDF 或整页扫描件',
    guidance: '上传人员证书、劳动合同等整页资料。身份证、签名等敏感信息需确认是否脱敏。',
  },
  {
    label: '社保证明',
    value: 'social_security',
    library: 'qualification',
    recommendedFormats: '完整 PDF 或整页扫描件',
    guidance: '上传社保证明、缴费证明等完整材料，避免只上传姓名或局部表格截图。',
  },
  {
    label: '项目业绩',
    value: 'project_performance',
    library: 'qualification',
    recommendedFormats: '合同、中标通知书、验收单 PDF/DOCX',
    guidance: '上传合同、中标通知书、验收单等完整材料，系统后续可提取项目名称、金额、数量和日期。',
  },
  {
    label: '合同证明',
    value: 'contract',
    library: 'qualification',
    recommendedFormats: '完整 PDF 或 DOCX',
    guidance: '上传完整合同或协议书，不要只上传签章页或金额局部截图。',
  },
  {
    label: '中标通知书',
    value: 'bid_award_notice',
    library: 'qualification',
    recommendedFormats: '完整 PDF 或整页扫描件',
    guidance: '上传完整中标通知书或成交通知书，招标编号、包号和中标金额应可追溯。',
  },
  {
    label: '授权文件',
    value: 'authorization',
    library: 'qualification',
    recommendedFormats: 'DOCX、PDF',
    guidance: '上传法人授权、制造商授权、投标授权等完整文件。签名/印章局部图不得单独作为正式资料。',
  },
  {
    label: '企业证明材料',
    value: 'enterprise_evidence',
    library: 'qualification',
    recommendedFormats: '完整 PDF、DOCX、整页扫描件',
    guidance: '上传无法归入上述类型但可证明企业能力或资质的完整材料。',
  },
];

const qualityLabels: Record<AssetQualityTier, { label: string; color: string }> = {
  formal_bid_ready: { label: '可用于标书正文', color: 'green' },
  knowledge_only: { label: '知识库/需复核', color: 'blue' },
  review_only: { label: '需人工复核', color: 'orange' },
  restricted: { label: '禁止使用', color: 'red' },
};

type AssetUsageSource = {
  metadata?: Record<string, unknown>;
  specs?: Record<string, unknown>;
};

function metadataValue(asset: AssetUsageSource, key: string): unknown {
  return asset.metadata?.[key] ?? asset.specs?.[key];
}

function truthyFlag(value: unknown): boolean {
  return value === true || value === 'true' || value === '1' || value === 1;
}

function falseFlag(value: unknown): boolean {
  return value === false || value === 'false' || value === '0' || value === 0;
}

export function assetUsageLabel(asset: AssetUsageSource): { label: string; color: string; tier: AssetQualityTier } {
  const qualityTier = metadataValue(asset, 'quality_tier');
  const explicit = typeof qualityTier === 'string' && qualityTier in qualityLabels
    ? assetQualityLabel(qualityTier)
    : null;
  if (explicit?.tier === 'restricted' || explicit?.tier === 'review_only') {
    return explicit;
  }

  const allowedForBid = metadataValue(asset, 'allowed_for_bid');
  const formalExcluded = metadataValue(asset, 'formal_bid_excluded');
  if (truthyFlag(formalExcluded) || falseFlag(allowedForBid)) {
    return { ...qualityLabels.knowledge_only, tier: 'knowledge_only' };
  }
  if (explicit) {
    return explicit;
  }
  return { ...qualityLabels.formal_bid_ready, tier: 'formal_bid_ready' };
}

const evidenceOptionMap = new Map(
  [...productEvidenceOptions, ...qualificationEvidenceOptions].map(option => [option.value, option]),
);

export function evidenceLabel(value?: string): string {
  if (!value) return '';
  return evidenceOptionMap.get(value)?.label || value;
}

export function evidenceValueFromLabel(label?: string): string | undefined {
  if (!label) return undefined;
  return [...evidenceOptionMap.values()].find(option => option.label === label || option.value === label)?.value;
}

export function assetQualityLabel(tier?: unknown): { label: string; color: string; tier: AssetQualityTier } {
  const normalized = typeof tier === 'string' && tier in qualityLabels ? tier as AssetQualityTier : 'knowledge_only';
  return { ...qualityLabels[normalized], tier: normalized };
}

export function optionForEvidence(value?: string): AssetEvidenceOption | undefined {
  return value ? evidenceOptionMap.get(value) : undefined;
}

function extensionOf(fileName: string): string {
  const parts = fileName.toLowerCase().split('.');
  return parts.length > 1 ? parts.pop() || '' : '';
}

function containsChinese(value: string): boolean {
  return /[\u4e00-\u9fff]/.test(value);
}

function looksInternalName(value: string): boolean {
  return /页面[_\-\s]*\d+|原图|taichang_|production_capacity|testing_capacity|green_low_carbon|business_license|certification|product_image|[0-9a-f]{8}-[0-9a-f-]{20,}/i.test(value);
}

function isImageExt(ext: string): boolean {
  return ['png', 'jpg', 'jpeg', 'webp'].includes(ext);
}

function isTableExt(ext: string): boolean {
  return ['xls', 'xlsx', 'csv'].includes(ext);
}

function isDocumentExt(ext: string): boolean {
  return ['pdf', 'doc', 'docx'].includes(ext);
}

function readImageSize(file: File): Promise<{ width: number; height: number } | null> {
  return new Promise(resolve => {
    if (!file.type.startsWith('image/')) {
      resolve(null);
      return;
    }
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      const size = { width: image.naturalWidth, height: image.naturalHeight };
      URL.revokeObjectURL(url);
      resolve(size);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(null);
    };
    image.src = url;
  });
}

export async function inspectUploadFile(file: File, evidenceType?: string): Promise<UploadQualityPreview> {
  const notes: string[] = [];
  const ext = extensionOf(file.name);
  const option = optionForEvidence(evidenceType);
  const size = await readImageSize(file);
  let tier: AssetQualityTier = 'formal_bid_ready';

  if (!containsChinese(file.name) || looksInternalName(file.name) || file.name.replace(/\.[^.]+$/, '').length < 4) {
    notes.push('文件名缺少清晰中文业务含义，系统会自动生成正式中文标题。');
  }

  if (option?.value === 'product_parameter_table' && !isTableExt(ext)) {
    notes.push('产品参数表建议上传原始 Excel 或 CSV，图片/截图会降低结构化抽取质量。');
    tier = 'review_only';
  }

  if (isTableExt(ext)) {
    notes.push('表格资料适合结构化抽取和知识问答，不作为正式标书图片自动插入。');
    tier = tier === 'review_only' ? tier : 'knowledge_only';
  } else if (!isImageExt(ext) && !isDocumentExt(ext)) {
    notes.push('文件格式不在推荐范围内，请确认是否为客户原始资料。');
    tier = 'review_only';
  }

  if (isImageExt(ext)) {
    if (file.size < 30 * 1024) {
      notes.push('图片文件较小，可能是截图、二维码或局部裁剪图，不建议直接用于正式标书。');
      tier = 'review_only';
    }
    if (size) {
      if (size.width < 800 || size.height < 600) {
        notes.push(`图片尺寸为 ${size.width}×${size.height}，建议上传更高清的原始照片或整页扫描件。`);
        tier = 'review_only';
      }
    }
  }

  if (/(二维码|印章|签名|页脚|截图|局部|裁剪)/.test(file.name)) {
    notes.push('疑似局部截图或签章类素材，默认需要人工复核，不自动进入正式标书。');
    tier = 'review_only';
  }

  if (!notes.length) {
    notes.push('文件格式和命名基本符合要求，保存后系统会生成正式中文展示字段。');
  }

  const label = assetQualityLabel(tier);
  return {
    tier,
    label: label.label,
    color: label.color,
    notes,
    width: size?.width,
    height: size?.height,
  };
}
