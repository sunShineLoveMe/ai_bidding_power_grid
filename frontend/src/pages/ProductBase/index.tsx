import { Button, Descriptions, Empty, Form, Input, Modal, Select, Space, Switch, Table, Tag, Upload, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { Box, Cpu, FileStack, Tags, UploadCloud } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CategoryList } from '../../components/common/CategoryList';
import { AuthenticatedImage, openAuthenticatedFile } from '../../components/common/AuthenticatedImage';
import { MetricCards } from '../../components/common/MetricCards';
import { ModuleHeader } from '../../components/common/ModuleHeader';
import { apiClient } from '../../api/client';
import { displayAssetCategory, displayAssetTags, displayAssetTitle } from '../../utils/assetDisplay';

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

const preferredCategories = [
  '电缆与附件',
  '开关柜与成套设备',
  '变压器与箱变',
  '互感器',
  '继电保护与自动化',
  '通信与调度设备',
  '产品实物图片',
  '生产制造能力',
  '试验检测设备',
  '检验报告',
  '绿色低碳资料',
  '厂房仓储资料',
  '输变电设备',
  '配网设备',
  '检测与试验设备',
  '安装调试服务',
  '运维检修服务',
  '安全工器具',
];

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

function scenario(asset: KnowledgeAsset): string {
  const volumes = applicableVolumes(asset).map(value => volumeLabelMap[value] || value).filter(Boolean);
  return volumes.slice(0, 2).join('、') || (asset.applicable_sections || []).slice(0, 2).join('、') || '技术标';
}

function versionLabel(asset: KnowledgeAsset): string {
  return asset.is_synthetic ? '脱敏样例' : '泰昌资料';
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

export function ProductBasePage(): JSX.Element {
  const [form] = Form.useForm();
  const [activeCategory, setActiveCategory] = useState('全部产品');
  const [assets, setAssets] = useState<KnowledgeAsset[]>([]);
  const [stats, setStats] = useState<KnowledgeAssetStats | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [assetFile, setAssetFile] = useState<File | null>(null);
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
        library_type: 'product',
        page: String(page),
        page_size: String(pageSize),
      });
      if (category !== '全部产品') {
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
      message.error(error.message || '获取产品资产失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets(1, pagination.pageSize, activeCategory);
  }, [activeCategory]);

  const categories = useMemo(() => {
    const counts = stats?.category_counts || {};
    const ordered = [
      ...preferredCategories,
      ...Object.keys(counts).filter(category => !preferredCategories.includes(category)).sort((a, b) => a.localeCompare(b, 'zh-CN')),
    ];
    return [
      { name: '全部产品', count: stats?.total || pagination.total },
      ...ordered.map(name => ({ name, count: counts[name] || 0 })),
    ];
  }, [pagination.total, stats]);

  const dataSource = assets;
  const tagCount = stats?.tag_count || 0;
  const materialCount = stats?.total || pagination.total;
  const customerAssetCount = stats?.customer_asset_count || 0;
  const metricValue = (value: number) => (loading && pagination.total === 0 ? '...' : value);

  const columns: ColumnsType<KnowledgeAsset> = [
    { title: '资料名称', dataIndex: 'title', ellipsis: true, render: (_, record) => displayAssetTitle(record) },
    { title: '类型', dataIndex: 'category', width: 150, render: (_, record) => <Tag color="blue">{displayAssetCategory(record) || '产品资料'}</Tag> },
    { title: '版本', width: 90, render: (_, record) => versionLabel(record) },
    { title: '适用场景', width: 180, ellipsis: true, render: (_, record) => scenario(record) },
    {
      title: '能力标签',
      dataIndex: 'tags',
      width: 230,
      render: (_, record) => (
        <Space size={4} wrap>
          {displayAssetTags(record).map(tag => <Tag key={tag}>{tag}</Tag>)}
        </Space>
      ),
    },
    { title: '资料数', width: 80, render: () => 1 },
    {
      title: '操作',
      width: 130,
      fixed: 'right',
      render: (_, record) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => setDetail(record)}>详情</Button>
          <Button type="link" size="small" onClick={() => openEditForm(record)}>编辑</Button>
        </Space>
      ),
    },
  ];

  const openCreateForm = () => {
    setEditingAsset(null);
    form.resetFields();
    setAssetFile(null);
    setFormOpen(true);
  };

  const openEditForm = (asset: KnowledgeAsset) => {
    setEditingAsset(asset);
    setAssetFile(null);
    form.setFieldsValue({
      title: asset.title,
      category: displayAssetCategory(asset),
      description: asset.description,
      product_model: asset.specs?.product_model,
      applicable_volumes: applicableVolumes(asset).length ? applicableVolumes(asset) : ['technical'],
      tags: asset.tags || [],
      applicable_sections: asset.applicable_sections || [],
      allowed_for_bid: asset.specs?.allowed_for_bid ?? true,
      usage_note: asset.specs?.usage_note,
    });
    setFormOpen(true);
  };

  const saveProductAsset = async () => {
    try {
      const values = await form.validateFields();
      if (!editingAsset && !assetFile) {
        message.warning('请先上传产品图片、图册或附件');
        return;
      }
      setSaving(true);
      const formData = new FormData();
      if (assetFile) {
        formData.append('file', assetFile);
      }
      formData.append('library_type', 'product');
      formData.append('asset_type', 'product_image');
      formData.append('title', values.title);
      formData.append('category', values.category);
      formData.append('description', values.description || '');
      formData.append('product_model', values.product_model || '');
      formData.append('applicable_volumes', JSON.stringify(values.applicable_volumes || ['technical']));
      formData.append('tags', JSON.stringify(values.tags || []));
      formData.append('applicable_sections', JSON.stringify(values.applicable_sections || []));
      formData.append('allowed_for_bid', String(values.allowed_for_bid ?? true));
      formData.append('is_sensitive', 'false');
      formData.append('anonymized', 'true');
      formData.append('usage_note', values.usage_note || '');
      const url = editingAsset ? `/api/knowledge/assets/${editingAsset.id}` : '/api/knowledge/assets/upload';
      const method = editingAsset ? 'patch' : 'post';
      await apiClient[method](url, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      message.success(editingAsset ? '产品资料已更新并刷新检索信息' : '产品资料已保存并接入检索');
      form.resetFields();
      setAssetFile(null);
      setEditingAsset(null);
      setFormOpen(false);
      await fetchAssets();
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error.message || '保存产品资料失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="module-shell">
      <ModuleHeader
        title="企业产品库"
        description="沉淀产品参数、图片、检验报告、制造能力和适用场景，上传后用于知识问答、技术标正文和标书配图。"
        actions={
          <Button type="primary" icon={<UploadCloud size={16} />} onClick={openCreateForm}>上传/新增产品资料</Button>
        }
      />
      <MetricCards
        items={[
          { title: '产品资料数', value: metricValue(stats?.total || pagination.total), desc: loading && pagination.total === 0 ? '正在加载产品资产' : '已接入产品资产', icon: Box, colorClass: 'bg-blue-50 text-blue-600' },
          { title: '能力标签', value: metricValue(tagCount), desc: loading && pagination.total === 0 ? '正在统计中文标签' : '来自产品资料标签', icon: Tags, colorClass: 'bg-emerald-50 text-emerald-600' },
          { title: '参数/图片素材', value: metricValue(materialCount), desc: loading && pagination.total === 0 ? '正在加载素材' : '检验报告、产品图片和参数素材', icon: Cpu, colorClass: 'bg-violet-50 text-violet-600' },
          { title: '客户资料', value: metricValue(customerAssetCount), desc: loading && pagination.total === 0 ? '正在加载泰昌素材' : '泰昌已提供素材', icon: FileStack, colorClass: 'bg-orange-50 text-orange-500' },
        ]}
      />
      <div className="grid min-h-0 grid-cols-[250px_minmax(0,1fr)] gap-4">
        <CategoryList title="产品分类" items={categories} activeName={activeCategory} onChange={setActiveCategory} />
        <section className="panel-card flex h-full min-h-0 flex-col overflow-hidden">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="panel-title mb-0">产品与服务列表</h2>
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
              scroll={{ x: 1050, y: 'max(180px, calc(100vh - 550px))' }}
              locale={{
                emptyText: loading ? (
                  <span className="text-xs font-semibold text-slate-500">正在加载产品资料...</span>
                ) : (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description={activeCategory === '全部产品' ? '暂无产品资料，请上传真实产品图片、参数表或检验报告' : `${activeCategory} 暂无资料，请上传客户真实资料后使用`}
                  />
                ),
              }}
            />
          </div>
        </section>
      </div>

      <Modal
        title={editingAsset ? '编辑产品资料' : '上传/新增产品资料'}
        open={formOpen}
        onCancel={() => {
          setFormOpen(false);
          setEditingAsset(null);
          setAssetFile(null);
        }}
        width={920}
        destroyOnHidden={false}
        footer={[
          <Button key="cancel" onClick={() => {
            setFormOpen(false);
            setEditingAsset(null);
            setAssetFile(null);
          }}>取消</Button>,
          <Button key="save" type="primary" loading={saving} onClick={saveProductAsset}>{editingAsset ? '保存修改' : '保存并接入检索'}</Button>,
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
                  <Box className="text-blue-500" size={42} />
                )}
              </div>
              <Descriptions size="small" column={1}>
                <Descriptions.Item label="当前资料">{displayAssetTitle(editingAsset)}</Descriptions.Item>
                <Descriptions.Item label="当前分类">{displayAssetCategory(editingAsset)}</Descriptions.Item>
                <Descriptions.Item label="原始文件">{editingAsset.file_name || '-'}</Descriptions.Item>
                <Descriptions.Item label="替换说明">如需替换，请选择新的图片或附件；不选择文件时仅更新名称、分类和标签。</Descriptions.Item>
              </Descriptions>
            </div>
          ) : null}
          <div className="grid gap-x-5 md:grid-cols-2">
            <Form.Item label="资料名称" name="title" rules={[{ required: true, message: '请输入资料名称' }]}>
              <Input placeholder="例如：CPVC电缆保护管检验报告（第1页）" />
            </Form.Item>
            <Form.Item label="资料分类" name="category" rules={[{ required: true, message: '请选择资料分类' }]}>
              <Select options={categories.slice(1).map(item => ({ label: item.name, value: item.name }))} placeholder="选择类型" />
            </Form.Item>
            <Form.Item label="规格型号" name="product_model">
              <Input placeholder="例如：DN800、Q235B、定制加工件" />
            </Form.Item>
          </div>
            <Form.Item label="适用分册" name="applicable_volumes" initialValue={['technical']} rules={[{ required: true, message: '请选择至少一个适用分册' }]}>
              <Select mode="multiple" options={volumeOptions} placeholder="用于控制 RAG 召回和自动插图范围" />
            </Form.Item>
            <Form.Item label="推荐插入章节" name="applicable_sections">
              <Select mode="multiple" options={['技术响应文件', '施工组织设计', '设备配置方案', '质量保证措施', '商务响应文件'].map(value => ({ label: value, value }))} />
            </Form.Item>
            <Form.Item label="核心能力标签" name="tags">
              <Select mode="tags" placeholder="输入能力标签" />
            </Form.Item>
            <Form.Item label="资料说明" name="description" rules={[{ required: true, message: '请输入说明，便于AI检索和插图' }]}>
              <Input.TextArea rows={3} placeholder="说明资料中的产品、规格、使用场景、关键参数，以及适合插入的标书章节；这些内容会进入知识问答和标书素材索引" />
            </Form.Item>
            <Form.Item label="图片/附件文件" required={!editingAsset}>
              <Upload
                maxCount={1}
                fileList={assetFile ? [{ uid: 'asset-file', name: assetFile.name, status: 'done' }] : editingAsset?.file_name ? [{ uid: 'asset-existing', name: editingAsset.file_name, status: 'done' }] : []}
                beforeUpload={(file) => {
                  setAssetFile(file);
                  return false;
                }}
                onRemove={() => setAssetFile(null)}
                accept="image/*,.pdf,.doc,.docx"
              >
                <Button icon={<UploadCloud size={16} />}>{editingAsset ? '替换产品图片或附件' : '选择产品图片或附件'}</Button>
              </Upload>
            </Form.Item>
            <Form.Item label="允许自动插入标书" name="allowed_for_bid" valuePropName="checked" initialValue>
              <Switch checkedChildren="允许" unCheckedChildren="仅检索" />
            </Form.Item>
            <Form.Item label="使用备注" name="usage_note">
              <Input placeholder="例如：适合技术响应配图，不作为资质证明材料" />
            </Form.Item>
        </Form>
      </Modal>

      <Modal title="产品资料详情" open={Boolean(detail)} onCancel={() => setDetail(null)} footer={<Button onClick={() => setDetail(null)}>关闭</Button>} width={900}>
        {detail ? (
          <div className="grid gap-4 md:grid-cols-[300px_1fr]">
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
                  <Box className="text-blue-500" size={42} />
                  <div className="text-sm font-bold text-slate-600">{detail.file_name || detail.title}</div>
                  <Button onClick={() => openAuthenticatedFile(assetFileUrl(detail))}>打开附件</Button>
                </div>
              ) : (
                <Empty description="无附件" />
              )}
            </div>
            <Descriptions size="small" bordered column={1}>
              <Descriptions.Item label="资料名称">{displayAssetTitle(detail)}</Descriptions.Item>
              <Descriptions.Item label="资料分类">{displayAssetCategory(detail) || '-'}</Descriptions.Item>
              <Descriptions.Item label="适用场景">{scenario(detail)}</Descriptions.Item>
              <Descriptions.Item label="适用分册">{applicableVolumes(detail).map(value => volumeLabelMap[value] || value).join('、') || '-'}</Descriptions.Item>
              <Descriptions.Item label="能力标签">{displayAssetTags(detail, 8).join('、') || '-'}</Descriptions.Item>
              <Descriptions.Item label="产品说明">{detail.description || '-'}</Descriptions.Item>
              <Descriptions.Item label="适用章节">{(detail.applicable_sections || []).join('、') || '-'}</Descriptions.Item>
              <Descriptions.Item label="来源">{detail.source_url ? <a href={detail.source_url} target="_blank" rel="noreferrer">查看来源</a> : '客户提供资料'}</Descriptions.Item>
              <Descriptions.Item label="合规说明">{detail.is_synthetic ? '脱敏合成样张，仅用于测试和排版占位。' : '泰昌客户自有资料，仅按泰昌租户内部投标场景使用。'}</Descriptions.Item>
            </Descriptions>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
