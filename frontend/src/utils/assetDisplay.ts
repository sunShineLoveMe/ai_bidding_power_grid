export interface AssetDisplayInput {
  title?: string;
  category?: string;
  tags?: string[];
  description?: string;
  metadata?: Record<string, unknown>;
  specs?: Record<string, unknown>;
}

const categoryLabelMap: Record<string, string> = {
  business_license: '基础证照',
  certification: '资质证书',
  enterprise_evidence: '企业证明材料',
  finance: '财务资料',
  green_low_carbon: '绿色低碳资料',
  inspection_report: '检验报告',
  personnel_certificate: '人员证书',
  production_capacity: '生产制造能力',
  testing_capacity: '试验检测能力',
  project_performance: '项目业绩',
  product_library: '产品库资料',
  qualification_library: '资信库资料',
  泰昌产品能力图片: '产品实物图片',
  泰昌资信图片: '资信资料',
};

const tagLabelMap: Record<string, string> = {
  production_capacity: '生产制造能力',
  testing_capacity: '试验检测能力',
  green_low_carbon: '绿色低碳资料',
  inspection_report: '检验报告',
  enterprise_evidence: '企业证明材料',
  product_image: '产品图片',
  qualification_image: '资信图片',
  MVP试点企业: '客户资料',
  泰昌企业事实: '企业自有资料',
  图片资产: '图片资料',
};

function textValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function hasPersonnelSignal(asset: AssetDisplayInput): boolean {
  const text = [
    asset.title,
    asset.category,
    asset.description,
    ...(asset.tags || []),
    textValue(asset.metadata?.evidence_type),
    textValue(asset.metadata?.evidence_type_label),
  ].join(' ');
  return /人员证书|人员花名册|劳动合同|社保|参保证明/.test(text);
}

function removeMeaninglessBrackets(value: string): string {
  return value
    .replace(/[（(]\s*[）)]/g, '')
    .replace(/[（(][\s,，、;；:：.．_\-—]*[）)]/g, '')
    .replace(/\s+[）)]/g, '')
    .replace(/[（(]\s+/g, '')
    .replace(/[，,。；;：:、.．_\-—\s]+$/g, '')
    .trim();
}

function normalizeTitle(rawTitle: string, asset: AssetDisplayInput): string {
  let title = rawTitle.trim();
  if (!title) return '';
  title = title
    .replace(/taichang_certification_[A-Za-z0-9_]+/gi, '泰昌资质证书资料')
    .replace(/taichang_production_capacity_[A-Za-z0-9_]+/gi, '泰昌生产制造能力资料')
    .replace(/taichang_testing_capacity_[A-Za-z0-9_]+/gi, '泰昌试验检测能力资料')
    .replace(/\bproduction_capacity\b/g, '生产制造能力')
    .replace(/\btesting_capacity\b/g, '试验检测能力')
    .replace(/\bcertification\b/g, '资质证书');
  title = title.replace(/^泰昌\s*([0-9]+[._、-]?)?/, '');
  title = title.replace(/^河北泰昌电力器材科技有限公司\s*/, '');
  title = title.replace(/\s+/g, '');
  title = title.replace(/Logo/g, ' Logo');
  title = title.replace(/第([0-9一二三四五六七八九十百]+)页$/, '（第$1页）');
  if (hasPersonnelSignal(asset) && !/人员证书|花名册|劳动合同|社保|参保证明/.test(title)) {
    title = title.replace(/（第([0-9一二三四五六七八九十百]+)页）$/, '人员证书（第$1页）');
  }
  title = removeMeaninglessBrackets(title);
  return title || rawTitle;
}

export function displayAssetTitle(asset: AssetDisplayInput): string {
  const metadataTitle = textValue(asset.metadata?.source_display_name);
  const title = normalizeTitle(metadataTitle || asset.title || '企业资料', asset);
  return title || '企业资料';
}

export function displayAssetCategory(asset: AssetDisplayInput): string {
  if (hasPersonnelSignal(asset)) return '人员证书';
  const metadata = asset.metadata || {};
  const candidates = [
    asset.category,
    textValue(metadata.evidence_type_label),
    textValue(metadata.category_label),
    textValue(metadata.evidence_type),
    textValue(metadata.target_library),
  ];
  for (const candidate of candidates) {
    const value = textValue(candidate);
    if (!value) continue;
    return categoryLabelMap[value] || value;
  }
  return '企业资料';
}

export function displayAssetTags(asset: AssetDisplayInput, limit = 3): string[] {
  const seen = new Set<string>();
  const visibleTags: string[] = [];
  for (const rawTag of asset.tags || []) {
    const tag = textValue(rawTag);
    if (!tag || /^taichang_/i.test(tag)) continue;
    const label = tagLabelMap[tag] || categoryLabelMap[tag] || tag;
    if (!label || /_/.test(label)) continue;
    if (seen.has(label)) continue;
    seen.add(label);
    visibleTags.push(label);
    if (visibleTags.length >= limit) break;
  }
  return visibleTags;
}
