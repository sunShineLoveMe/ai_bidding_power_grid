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

function normalizeTitle(rawTitle: string, asset: AssetDisplayInput): string {
  let title = rawTitle.trim();
  if (!title) return '';
  title = title.replace(/^泰昌\s*([0-9]+[._、-]?)?/, '');
  title = title.replace(/^河北泰昌电力器材科技有限公司\s*/, '');
  title = title.replace(/\s+/g, '');
  title = title.replace(/Logo/g, ' Logo');
  title = title.replace(/第([0-9一二三四五六七八九十百]+)页$/, '（第$1页）');
  if (hasPersonnelSignal(asset) && !/人员证书|花名册|劳动合同|社保|参保证明/.test(title)) {
    title = title.replace(/（第([0-9一二三四五六七八九十百]+)页）$/, '人员证书（第$1页）');
  }
  return title || rawTitle;
}

export function displayAssetTitle(asset: AssetDisplayInput): string {
  const metadataTitle = textValue(asset.metadata?.source_display_name);
  const title = normalizeTitle(asset.title || metadataTitle || '企业资料', asset);
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
