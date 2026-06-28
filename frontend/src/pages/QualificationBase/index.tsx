import { Alert, Button, Descriptions, Empty, Form, Input, Modal, Select, Space, Switch, Table, Tag, Upload, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { AlertTriangle, BadgeCheck, CalendarClock, FileBadge, UploadCloud } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CategoryList } from '../../components/common/CategoryList';
import { AuthenticatedImage, openAuthenticatedFile } from '../../components/common/AuthenticatedImage';
import { MetricCards } from '../../components/common/MetricCards';
import { ModuleHeader } from '../../components/common/ModuleHeader';
import { apiClient } from '../../api/client';
import { displayAssetCategory, displayAssetTitle } from '../../utils/assetDisplay';
import {
  assetUsageLabel,
  evidenceLabel,
  evidenceValueFromLabel,
  inspectUploadFile,
  optionForEvidence,
  qualificationEvidenceOptions,
  type UploadQualityPreview,
} from '../../utils/assetUploadGuidance';

interface KnowledgeAsset {
  id: string;
  title: string;
  description?: string;
  category?: string;
  asset_type: string;
  public_url?: string;
  source_url?: string;
  file_name?: string;
  mime_type?: string;
  storage_path?: string;
  license?: string;
  attribution?: string;
  applicable_volumes?: string[];
  applicable_sections?: string[];
  tags?: string[];
  specs?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  status?: string;
  is_synthetic?: boolean;
  anonymized?: boolean;
  created_at?: string;
}

interface KnowledgeAssetStats {
  total: number;
  indexed_count: number;
  synthetic_count: number;
  customer_asset_count: number;
  category_counts: Record<string, number>;
  tag_count: number;
}

interface KnowledgeAssetPageResponse {
  items: KnowledgeAsset[];
  total: number;
  page: number;
  page_size: number;
  stats?: KnowledgeAssetStats;
}

const categoryMap: Record<string, string> = {
  企业资信: '企业资信',
  基础证照: '基础证照',
  资质证书: '资质证书',
  人员证书: '人员证书',
  财务资料: '财务资料',
  项目业绩: '项目业绩',
  授权模板: '授权模板',
  绿色低碳资料: '绿色低碳资料',
};

const volumeOptions = [
  { label: '技术标', value: 'technical' },
  { label: '商务标', value: 'business' },
  { label: '资格文件', value: 'qualification' },
  { label: '报价文件', value: 'price' },
  { label: '附件材料', value: 'attachment' },
];

const volumeLabelMap: Record<string, string> = Object.fromEntries(volumeOptions.map(item => [item.value, item.label]));

function applicableVolumes(asset: KnowledgeAsset): string[] {
  const specs = asset.specs || {};
  const values = asset.applicable_volumes || (specs.applicable_volumes as string[] | undefined) || [];
  return Array.isArray(values) ? values : [];
}

function inferQualificationCategory(asset: KnowledgeAsset): string {
  const displayCategory = displayAssetCategory(asset);
  if (categoryMap[displayCategory]) return displayCategory;
  const text = `${asset.title || ''} ${(asset.tags || []).join('、')} ${asset.description || ''}`;
  if (text.includes('营业执照')) return '基础证照';
  if (text.includes('开户许可证')) return '基础证照';
  if (text.includes('资质')) return '资质证书';
  if (text.includes('认证证书')) return '资质证书';
  if (text.includes('安全生产许可证')) return '资质证书';
  if (text.includes('财务') || text.includes('审计报告')) return '财务资料';
  if (text.includes('绿色') || text.includes('低碳') || text.includes('ESG')) return '绿色低碳资料';
  return categoryMap[asset.category || ''] || '企业资信';
}

function statusLabel(asset: KnowledgeAsset): string {
  if (asset.status === 'indexed') return '有效';
  if (asset.status === 'processing') return '待核验';
  return '待核验';
}

function assetFileUrl(asset: KnowledgeAsset): string {
  return `/api/knowledge/assets/${asset.id}/file`;
}

function assetThumbnailUrl(asset: KnowledgeAsset): string {
  return `/api/knowledge/assets/${asset.id}/file?variant=thumb`;
}

function isImageAsset(asset: KnowledgeAsset): boolean {
  return (asset.mime_type || '').startsWith('image/');
}

function metadataText(asset: KnowledgeAsset, key: string): string {
  const value = asset.metadata?.[key] ?? asset.specs?.[key];
  return typeof value === 'string' ? value : '';
}

function metadataList(asset: KnowledgeAsset, key: string): string[] {
  const value = asset.metadata?.[key] ?? asset.specs?.[key];
  if (Array.isArray(value)) return value.map(item => String(item)).filter(Boolean);
  if (typeof value === 'string' && value.trim()) return [value.trim()];
  return [];
}

function assetQuality(asset: KnowledgeAsset) {
  return assetUsageLabel(asset);
}

function assetEvidenceType(asset: KnowledgeAsset): string {
  return metadataText(asset, 'evidence_type') || evidenceValueFromLabel(displayAssetCategory(asset)) || 'certification';
}

const statusColor: Record<string, string> = {
  有效: 'green',
  临期: 'orange',
  待核验: 'blue',
};

export function QualificationBasePage(): JSX.Element {
  const [form] = Form.useForm();
  const selectedEvidenceType = Form.useWatch('evidence_type', form);
  const [activeCategory, setActiveCategory] = useState('全部资信');
  const [assets, setAssets] = useState<KnowledgeAsset[]>([]);
  const [stats, setStats] = useState<KnowledgeAssetStats | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [assetFile, setAssetFile] = useState<File | null>(null);
  const [uploadReview, setUploadReview] = useState<UploadQualityPreview | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingAsset, setEditingAsset] = useState<KnowledgeAsset | null>(null);
  const [detail, setDetail] = useState<KnowledgeAsset | null>(null);

  const fetchAssets = async (
    page = pagination.current,
    pageSize = pagination.pageSize,
    category = activeCategory,
  ) => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        library_type: 'qualification',
        page: String(page),
        page_size: String(pageSize),
      });
      if (category !== '全部资信') {
        params.set('category', category);
      }
      const { data } = await apiClient.get<KnowledgeAssetPageResponse>(`/api/knowledge/assets?${params.toString()}`, {
        skipGlobalLoading: true,
      });
      setAssets(data.items || []);
      setStats(data.stats || null);
      setPagination({
        current: data.page || page,
        pageSize: data.page_size || pageSize,
        total: data.total || 0,
      });
    } catch (error: any) {
      message.error(error.message || '获取资信资产失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets(1, pagination.pageSize, activeCategory);
  }, [activeCategory]);

  useEffect(() => {
    let cancelled = false;
    if (!assetFile) {
      setUploadReview(null);
      return () => {
        cancelled = true;
      };
    }
    inspectUploadFile(assetFile, selectedEvidenceType).then(result => {
      if (!cancelled) setUploadReview(result);
    });
    return () => {
      cancelled = true;
    };
  }, [assetFile, selectedEvidenceType]);

  const enrichedAssets = useMemo(
    () => assets.map(asset => ({ ...asset, qualificationCategory: inferQualificationCategory(asset) })),
    [assets],
  );

  const categories = useMemo(() => {
    const counts = stats?.category_counts || {};
    const preferredNames = ['基础证照', '资质证书', '人员证书', '财务资料', '绿色低碳资料', '项目业绩', '授权模板'];
    const names = [
      ...preferredNames,
      ...Object.keys(counts).filter(name => !preferredNames.includes(name)).sort((a, b) => a.localeCompare(b, 'zh-CN')),
    ];
    return [
      { name: '全部资信', count: stats?.total || pagination.total },
      ...names.map(name => ({ name, count: counts[name] || 0 })),
    ];
  }, [pagination.total, stats]);

  const dataSource = enrichedAssets;
  const metricValue = (value: number) => (loading && pagination.total === 0 ? '...' : value);
  const selectedEvidenceOption = optionForEvidence(selectedEvidenceType);

  const columns: ColumnsType<KnowledgeAsset & { qualificationCategory?: string }> = [
    { title: '资信文件', dataIndex: 'title', ellipsis: true, render: (_, record) => displayAssetTitle(record) },
    { title: '分类', dataIndex: 'qualificationCategory', width: 110, render: value => <Tag color="purple">{value}</Tag> },
    { title: '使用范围', width: 130, render: (_, record) => <Tag color={assetQuality(record).color}>{assetQuality(record).label}</Tag> },
    { title: '发证/出具机构', dataIndex: 'attribution', width: 150, ellipsis: true, render: value => value || '脱敏样张' },
    { title: '编号', width: 130, render: (_, record) => (record.is_synthetic ? '脱敏样例' : '-') },
    { title: '有效期', width: 110, render: () => '待维护' },
    { title: '状态', width: 90, render: (_, record) => <Tag color={statusColor[statusLabel(record)]}>{statusLabel(record)}</Tag> },
    {
      title: '操作',
      width: 130,
      fixed: 'right',
      render: (_, record) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => setDetail(record)}>查看</Button>
          <Button type="link" size="small" onClick={() => openEditForm(record)}>编辑</Button>
        </Space>
      ),
    },
  ];

  const openCreateForm = () => {
    setEditingAsset(null);
    form.resetFields();
    form.setFieldsValue({ evidence_type: 'certification', applicable_volumes: ['qualification', 'business', 'attachment'], allowed_for_bid: true, is_sensitive: false });
    setAssetFile(null);
    setUploadReview(null);
    setFormOpen(true);
  };

  const openEditForm = (asset: KnowledgeAsset) => {
    setEditingAsset(asset);
    setAssetFile(null);
    setUploadReview(null);
    form.setFieldsValue({
      title: asset.title,
      evidence_type: assetEvidenceType(asset),
      description: asset.description,
      certificate_no: asset.specs?.certificate_no,
      issuer: asset.specs?.issuer,
      applicable_volumes: applicableVolumes(asset).length ? applicableVolumes(asset) : ['qualification', 'business', 'attachment'],
      tags: asset.tags || [],
      applicable_sections: asset.applicable_sections || [],
      allowed_for_bid: asset.specs?.allowed_for_bid ?? true,
      is_sensitive: false,
      usage_note: asset.specs?.usage_note,
    });
    setFormOpen(true);
  };

  const saveQualificationAsset = async () => {
    try {
      const values = await form.validateFields();
      if (!editingAsset && !assetFile) {
        message.warning('请先上传证照图片或附件');
        return;
      }
      setSaving(true);
      const formData = new FormData();
      if (assetFile) {
        formData.append('file', assetFile);
      }
      formData.append('library_type', 'qualification');
      formData.append('asset_type', 'qualification_image');
      formData.append('title', values.title);
      formData.append('evidence_type', values.evidence_type);
      formData.append('category', evidenceLabel(values.evidence_type) || '企业资信');
      formData.append('description', values.description || '');
      formData.append('certificate_no', values.certificate_no || '');
      formData.append('issuer', values.issuer || '');
      formData.append('applicable_volumes', JSON.stringify(values.applicable_volumes || ['qualification']));
      formData.append('tags', JSON.stringify(values.tags || []));
      formData.append('applicable_sections', JSON.stringify(values.applicable_sections || []));
      formData.append('allowed_for_bid', String(values.allowed_for_bid ?? true));
      formData.append('is_sensitive', String(values.is_sensitive ?? false));
      formData.append('anonymized', 'true');
      formData.append('usage_note', values.usage_note || '');
      const url = editingAsset ? `/api/knowledge/assets/${editingAsset.id}` : '/api/knowledge/assets/upload';
      const method = editingAsset ? 'patch' : 'post';
      await apiClient[method](url, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      message.success(editingAsset ? '资信资料已更新并刷新检索信息' : '资信资料已保存并接入检索');
      form.resetFields();
      setAssetFile(null);
      setUploadReview(null);
      setEditingAsset(null);
      setFormOpen(false);
      await fetchAssets();
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error.message || '保存资信资料失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="module-shell">
      <ModuleHeader
        title="企业资信库"
        description="维护营业执照、资质证书、人员证书、财务资料、项目业绩和授权模板，上传后用于知识问答、商务标和资格文件。"
        actions={
          <Button type="primary" icon={<UploadCloud size={16} />} onClick={openCreateForm}>上传/新增资信资料</Button>
        }
      />
      <MetricCards
        items={[
          { title: '资信文件数', value: metricValue(stats?.total || pagination.total), desc: loading && pagination.total === 0 ? '正在加载资信资产' : '已接入资信资产', icon: FileBadge, colorClass: 'bg-blue-50 text-blue-600' },
          { title: '有效证照', value: metricValue(stats?.indexed_count || 0), desc: loading && pagination.total === 0 ? '正在检查索引状态' : '可用于检索', icon: BadgeCheck, colorClass: 'bg-emerald-50 text-emerald-600' },
          { title: '临期提醒', value: 0, desc: '待接入到期字段', icon: CalendarClock, colorClass: 'bg-orange-50 text-orange-500' },
          { title: '待核验资料', value: metricValue(Math.max((stats?.total || 0) - (stats?.indexed_count || 0), 0)), desc: loading && pagination.total === 0 ? '正在加载核验状态' : '需人工复核', icon: AlertTriangle, colorClass: 'bg-red-50 text-red-500' },
        ]}
      />
      <div className="grid min-h-0 grid-cols-[250px_minmax(0,1fr)] gap-4">
        <CategoryList title="资信分类" items={categories} activeName={activeCategory} onChange={setActiveCategory} />
        <section className="panel-card flex h-full min-h-0 flex-col overflow-hidden">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="panel-title mb-0">资信文件列表</h2>
            <span className="text-xs font-semibold text-slate-400">资料保存后自动接入检索索引</span>
          </div>
          <div className="bounded-table min-h-0 flex-1">
            <Table
              rowKey="id"
              size="small"
              pagination={{
                current: pagination.current,
                pageSize: pagination.pageSize,
                total: pagination.total,
                showSizeChanger: true,
                pageSizeOptions: [10, 20, 50],
                showTotal: total => `共 ${total} 条`,
              }}
              onChange={(nextPagination) => {
                fetchAssets(Number(nextPagination.current || 1), Number(nextPagination.pageSize || pagination.pageSize), activeCategory);
              }}
              columns={columns}
              dataSource={dataSource}
              loading={loading}
              className="compact-table"
              tableLayout="fixed"
              scroll={{ x: 1000, y: 'max(180px, calc(100vh - 550px))' }}
              locale={{
                emptyText: loading ? (
                  <span className="text-xs font-semibold text-slate-500">正在加载资信资料...</span>
                ) : (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description={activeCategory === '全部资信' ? '暂无资信文件，请上传真实证照、业绩或授权材料' : `${activeCategory} 暂无资料，请上传客户真实资料后使用`}
                  />
                ),
              }}
            />
          </div>
        </section>
      </div>

      <Modal
        title={editingAsset ? '编辑资信资料' : '上传/新增资信资料'}
        open={formOpen}
        onCancel={() => {
          setFormOpen(false);
          setEditingAsset(null);
          setAssetFile(null);
          setUploadReview(null);
        }}
        width={920}
        destroyOnHidden={false}
        footer={[
          <Button key="cancel" onClick={() => {
            setFormOpen(false);
            setEditingAsset(null);
            setAssetFile(null);
            setUploadReview(null);
          }}>取消</Button>,
          <Button key="save" type="primary" loading={saving} onClick={saveQualificationAsset}>{editingAsset ? '保存修改' : '保存并接入检索'}</Button>,
        ]}
      >
        <Form form={form} layout="vertical" size="middle" className="compact-form">
          {editingAsset ? (
            <div className="mb-4 grid gap-4 rounded-lg border border-slate-200 bg-slate-50 p-3 md:grid-cols-[220px_1fr]">
              <div className="flex min-h-36 items-center justify-center overflow-hidden rounded-md bg-white">
                {isImageAsset(editingAsset) ? (
                  <AuthenticatedImage
                    src={assetThumbnailUrl(editingAsset)}
                    alt={displayAssetTitle(editingAsset)}
                    className="max-h-52 object-contain"
                    previewSrc={assetFileUrl(editingAsset)}
                    fallback="/assets/brand-logo.png"
                  />
                ) : (
                  <FileBadge className="text-blue-500" size={42} />
                )}
              </div>
              <Descriptions size="small" column={1}>
                <Descriptions.Item label="当前资料">{displayAssetTitle(editingAsset)}</Descriptions.Item>
                <Descriptions.Item label="当前分类">{inferQualificationCategory(editingAsset)}</Descriptions.Item>
                <Descriptions.Item label="使用范围"><Tag color={assetQuality(editingAsset).color}>{assetQuality(editingAsset).label}</Tag></Descriptions.Item>
                <Descriptions.Item label="原始文件">{editingAsset.file_name || '-'}</Descriptions.Item>
                <Descriptions.Item label="替换说明">如需替换，请选择新的图片或附件；不选择文件时仅更新名称、分类和标签。</Descriptions.Item>
              </Descriptions>
            </div>
          ) : null}
          <div className="grid gap-x-5 md:grid-cols-2">
            <Form.Item label="资信名称" name="title" rules={[{ required: true, message: '请输入资信名称' }]}>
              <Input placeholder="例如：承装（修、试）电力设施许可证" />
            </Form.Item>
            <Form.Item label="资料类型" name="evidence_type" initialValue="certification" rules={[{ required: true, message: '请选择资料类型' }]}>
              <Select options={qualificationEvidenceOptions.map(item => ({ label: item.label, value: item.value }))} />
            </Form.Item>
            <Form.Item label="证书编号" name="certificate_no">
              <Input placeholder="请输入证书编号，可填写脱敏编号" />
            </Form.Item>
            <Form.Item label="发证/出具机构" name="issuer">
              <Input placeholder="请输入机构名称，可填写脱敏机构" />
            </Form.Item>
          </div>
            {selectedEvidenceOption ? (
              <Alert
                className="mb-4"
                type={selectedEvidenceOption.warning ? 'warning' : 'info'}
                showIcon
                message={`${selectedEvidenceOption.label}：推荐 ${selectedEvidenceOption.recommendedFormats}`}
                description={selectedEvidenceOption.warning ? `${selectedEvidenceOption.guidance} ${selectedEvidenceOption.warning}` : selectedEvidenceOption.guidance}
              />
            ) : null}
            <Form.Item label="适用分册" name="applicable_volumes" initialValue={['qualification', 'business', 'attachment']} rules={[{ required: true, message: '请选择至少一个适用分册' }]}>
              <Select mode="multiple" placeholder="用于控制 RAG 召回和自动插图范围" options={volumeOptions} />
            </Form.Item>
            <Form.Item label="适用投标场景" name="applicable_sections">
              <Select mode="multiple" placeholder="选择场景" options={['资格审查资料', '商务响应文件', '企业概况', '发包人提供的资料', '项目业绩'].map(value => ({ label: value, value }))} />
            </Form.Item>
            <Form.Item label="检索标签" name="tags">
              <Select mode="tags" placeholder="例如：资质证书、安全生产许可证、资格审查" />
            </Form.Item>
            <Form.Item label="资料说明" name="description" rules={[{ required: true, message: '请输入资料说明，便于AI检索和插图' }]}>
              <Input.TextArea rows={3} placeholder="说明该资料适合出现在哪类标书章节、关键编号或有效期、是否敏感、使用注意事项；这些内容会进入知识问答和标书素材索引" />
            </Form.Item>
            <Form.Item label="图片/附件文件" required={!editingAsset}>
              <Upload
                maxCount={1}
                fileList={assetFile ? [{ uid: 'asset-file', name: assetFile.name, status: 'done' }] : editingAsset?.file_name ? [{ uid: 'asset-existing', name: editingAsset.file_name, status: 'done' }] : []}
                beforeUpload={(file) => {
                  setAssetFile(file);
                  return false;
                }}
                onRemove={() => {
                  setAssetFile(null);
                  setUploadReview(null);
                }}
                accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.csv"
              >
                <Button icon={<UploadCloud size={16} />}>{editingAsset ? '替换证照图片或附件' : '选择证照图片或附件'}</Button>
              </Upload>
            </Form.Item>
            {uploadReview ? (
              <Alert
                className="mb-4"
                type={uploadReview.tier === 'formal_bid_ready' ? 'success' : uploadReview.tier === 'knowledge_only' ? 'info' : 'warning'}
                showIcon
                message={`资料预检：${uploadReview.label}`}
                description={uploadReview.notes.join('；')}
              />
            ) : null}
            <Form.Item label="允许自动插入标书" name="allowed_for_bid" valuePropName="checked" initialValue>
              <Switch checkedChildren="允许" unCheckedChildren="仅检索" />
            </Form.Item>
            <Form.Item label="敏感资料" name="is_sensitive" valuePropName="checked" initialValue={false}>
              <Switch checkedChildren="敏感" unCheckedChildren="普通" />
            </Form.Item>
            <Form.Item label="使用备注" name="usage_note">
              <Input placeholder="例如：正式投标前需替换为企业真实证照扫描件" />
            </Form.Item>
        </Form>
      </Modal>

      <Modal title="资信文件详情" open={Boolean(detail)} onCancel={() => setDetail(null)} footer={<Button onClick={() => setDetail(null)}>关闭</Button>} width={860}>
        {detail ? (
          <div className="grid gap-4 md:grid-cols-[260px_1fr]">
            <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
              {isImageAsset(detail) ? (
                <AuthenticatedImage
                  src={assetThumbnailUrl(detail)}
                  alt={detail.title}
                  className="rounded-lg object-contain"
                  previewSrc={assetFileUrl(detail)}
                  fallback="/assets/brand-logo.png"
                />
              ) : detail.storage_path || detail.public_url ? (
                <div className="flex h-full min-h-48 flex-col items-center justify-center gap-3 text-center">
                  <FileBadge className="text-blue-500" size={42} />
                  <div className="text-sm font-bold text-slate-600">{detail.file_name || detail.title}</div>
                  <Button onClick={() => openAuthenticatedFile(assetFileUrl(detail))}>打开附件</Button>
                </div>
              ) : (
                <Empty description="无附件" />
              )}
            </div>
            <Descriptions size="small" bordered column={1}>
              <Descriptions.Item label="文件名称">{displayAssetTitle(detail)}</Descriptions.Item>
              <Descriptions.Item label="分类">{inferQualificationCategory(detail)}</Descriptions.Item>
              <Descriptions.Item label="使用范围"><Tag color={assetQuality(detail).color}>{assetQuality(detail).label}</Tag></Descriptions.Item>
              <Descriptions.Item label="质量提示">{metadataList(detail, 'quality_notes').join('；') || '-'}</Descriptions.Item>
              <Descriptions.Item label="适用分册">{applicableVolumes(detail).map(value => volumeLabelMap[value] || value).join('、') || '-'}</Descriptions.Item>
              <Descriptions.Item label="说明">{detail.description || '-'}</Descriptions.Item>
              <Descriptions.Item label="适用章节">{(detail.applicable_sections || []).join('、') || '-'}</Descriptions.Item>
              <Descriptions.Item label="标签">{(detail.tags || []).join('、') || '-'}</Descriptions.Item>
              <Descriptions.Item label="来源">{detail.source_url ? <a href={detail.source_url} target="_blank" rel="noreferrer">查看来源</a> : '客户提供资料'}</Descriptions.Item>
              <Descriptions.Item label="合规说明">{detail.is_synthetic ? '脱敏合成样张，仅用于测试和排版占位，不可替代正式法定资质文件。' : '泰昌客户自有资料，仅按泰昌租户内部投标场景使用。'}</Descriptions.Item>
            </Descriptions>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
