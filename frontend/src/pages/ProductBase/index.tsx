import { Button, Descriptions, Empty, Form, Image, Input, Modal, Select, Space, Switch, Table, Tag, Upload, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { Box, Cpu, FileStack, Tags, UploadCloud } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CategoryList } from '../../components/common/CategoryList';
import { MetricCards } from '../../components/common/MetricCards';
import { ModuleHeader } from '../../components/common/ModuleHeader';
import { apiClient } from '../../api/client';

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
  status?: string;
  is_synthetic?: boolean;
  created_at?: string;
}

const preferredCategories = [
  '水轮机与水电设备',
  '紧固件与标准件',
  '泵站设备',
  '金属结构与闸门',
  '阀门与管件',
  '水利信息化产品',
  '电气与自动化',
  '检测与试验设备',
  '泵站水闸工程',
  '灌区与渠道工程',
  '水库除险加固',
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
  return asset.is_synthetic ? '脱敏样例' : '公开素材';
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
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [assetFile, setAssetFile] = useState<File | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingAsset, setEditingAsset] = useState<KnowledgeAsset | null>(null);
  const [detail, setDetail] = useState<KnowledgeAsset | null>(null);

  const fetchAssets = async () => {
    try {
      setLoading(true);
      const { data } = await apiClient.get<KnowledgeAsset[]>('/api/knowledge/assets?asset_type=product_image', {
        skipGlobalLoading: true,
      });
      setAssets(data);
    } catch (error: any) {
      message.error(error.message || '获取产品资产失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
  }, []);

  const categories = useMemo(() => {
    const counts = assets.reduce<Record<string, number>>((acc, asset) => {
      const category = asset.category || '其他产品资料';
      acc[category] = (acc[category] || 0) + 1;
      return acc;
    }, {});
    const ordered = [
      ...preferredCategories.filter(category => counts[category]),
      ...Object.keys(counts).filter(category => !preferredCategories.includes(category)).sort((a, b) => a.localeCompare(b, 'zh-CN')),
    ];
    return [
      { name: '全部产品', count: assets.length },
      ...ordered.map(name => ({ name, count: counts[name] || 0 })),
    ];
  }, [assets]);

  const dataSource = activeCategory === '全部产品' ? assets : assets.filter(asset => asset.category === activeCategory);
  const tagCount = new Set(assets.flatMap(asset => asset.tags || [])).size;
  const specCount = assets.filter(asset => asset.is_synthetic || Object.keys(asset.specs || {}).length > 0).length;
  const publicCaseCount = assets.filter(asset => !asset.is_synthetic && asset.source_url).length;

  const columns: ColumnsType<KnowledgeAsset> = [
    { title: '产品/服务名称', dataIndex: 'title', ellipsis: true },
    { title: '类型', dataIndex: 'category', width: 150, render: value => <Tag color="blue">{value || '产品资料'}</Tag> },
    { title: '版本', width: 90, render: (_, record) => versionLabel(record) },
    { title: '适用场景', width: 180, ellipsis: true, render: (_, record) => scenario(record) },
    {
      title: '能力标签',
      dataIndex: 'tags',
      width: 230,
      render: tags => (
        <Space size={4} wrap>
          {((tags as string[]) || []).slice(0, 3).map(tag => <Tag key={tag}>{tag}</Tag>)}
        </Space>
      ),
    },
    { title: '资料数', width: 80, render: () => 1 },
    {
      title: '操作',
      width: 130,
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
      category: asset.category,
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
        description="沉淀产品参数、制造能力、适用场景、案例资料和服务能力，为技术响应和商务材料生成提供标准素材。"
        actions={
          <>
            <Button onClick={() => {
              openCreateForm();
            }}>新增产品</Button>
            <Upload showUploadList={false} beforeUpload={(file) => {
              setEditingAsset(null);
              form.resetFields();
              setAssetFile(file);
              setFormOpen(true);
              message.success('已选择文件，请补充产品信息后保存');
              return false;
            }}>
              <Button type="primary" icon={<UploadCloud size={16} />}>上传产品资料</Button>
            </Upload>
          </>
        }
      />
      <MetricCards
        items={[
          { title: '产品资料数', value: assets.length, desc: '已接入产品资产', icon: Box, colorClass: 'bg-blue-50 text-blue-600' },
          { title: '能力标签', value: tagCount, desc: '来自图片资产标签', icon: Tags, colorClass: 'bg-emerald-50 text-emerald-600' },
          { title: '技术参数表', value: specCount, desc: '规格图与参数素材', icon: Cpu, colorClass: 'bg-violet-50 text-violet-600' },
          { title: '案例附件', value: publicCaseCount, desc: '公开来源图片', icon: FileStack, colorClass: 'bg-orange-50 text-orange-500' },
        ]}
      />
      <div className="grid min-h-0 grid-cols-[250px_minmax(0,1fr)] gap-4">
        <CategoryList title="产品分类" items={categories} activeName={activeCategory} onChange={setActiveCategory} />
        <section className="panel-card flex h-full min-h-0 flex-col overflow-hidden">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="panel-title mb-0">产品与服务列表</h2>
            <Button type="primary" icon={<UploadCloud size={16} />} onClick={openCreateForm}>新增产品资料</Button>
          </div>
          <Table
            rowKey="id"
            size="small"
            pagination={{ pageSize: 10, showSizeChanger: true, pageSizeOptions: [10, 20, 50], showTotal: total => `共 ${total} 条` }}
            columns={columns}
            dataSource={dataSource}
            loading={loading}
            className="compact-table"
            tableLayout="fixed"
            scroll={{ y: 'calc(100vh - 430px)' }}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无产品资料，请维护真实产品信息" /> }}
          />
        </section>
      </div>

      <Modal
        title={editingAsset ? '编辑产品资料' : '产品能力维护'}
        open={formOpen}
        onCancel={() => {
          setFormOpen(false);
          setEditingAsset(null);
          setAssetFile(null);
        }}
        width={920}
        destroyOnClose={false}
        footer={[
          <Button key="cancel" onClick={() => {
            setFormOpen(false);
            setEditingAsset(null);
            setAssetFile(null);
          }}>取消</Button>,
          <Button key="save" type="primary" loading={saving} onClick={saveProductAsset}>{editingAsset ? '保存修改' : '保存产品信息'}</Button>,
        ]}
      >
        <Form form={form} layout="vertical" size="middle" className="compact-form">
          <div className="grid gap-x-5 md:grid-cols-2">
            <Form.Item label="产品名称" name="title" rules={[{ required: true, message: '请输入产品名称' }]}>
              <Input placeholder="例如：水轮机叶片精密加工件" />
            </Form.Item>
            <Form.Item label="产品类型" name="category" rules={[{ required: true, message: '请选择产品类型' }]}>
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
            <Form.Item label="产品图片/图册说明" name="description" rules={[{ required: true, message: '请输入说明，便于AI检索和插图' }]}>
              <Input.TextArea rows={3} placeholder="说明图片中的产品、规格、使用场景，以及适合插入的标书章节" />
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
                <Image
                  src={assetThumbnailUrl(detail)}
                  alt={detail.title}
                  className="rounded-lg object-contain"
                  preview={{ src: assetFileUrl(detail) }}
                  fallback="/assets/brand-logo.png"
                />
              ) : detail.storage_path || detail.public_url ? (
                <div className="flex h-full min-h-48 flex-col items-center justify-center gap-3 text-center">
                  <Box className="text-blue-500" size={42} />
                  <div className="text-sm font-bold text-slate-600">{detail.file_name || detail.title}</div>
                  <Button href={assetFileUrl(detail)} target="_blank">打开附件</Button>
                </div>
              ) : (
                <Empty description="无附件" />
              )}
            </div>
            <Descriptions size="small" bordered column={1}>
              <Descriptions.Item label="产品名称">{detail.title}</Descriptions.Item>
              <Descriptions.Item label="产品分类">{detail.category || '-'}</Descriptions.Item>
              <Descriptions.Item label="适用场景">{scenario(detail)}</Descriptions.Item>
              <Descriptions.Item label="适用分册">{applicableVolumes(detail).map(value => volumeLabelMap[value] || value).join('、') || '-'}</Descriptions.Item>
              <Descriptions.Item label="能力标签">{(detail.tags || []).join('、') || '-'}</Descriptions.Item>
              <Descriptions.Item label="产品说明">{detail.description || '-'}</Descriptions.Item>
              <Descriptions.Item label="适用章节">{(detail.applicable_sections || []).join('、') || '-'}</Descriptions.Item>
              <Descriptions.Item label="来源">{detail.source_url ? <a href={detail.source_url} target="_blank" rel="noreferrer">查看来源</a> : '脱敏合成规格图'}</Descriptions.Item>
              <Descriptions.Item label="合规说明">{detail.is_synthetic ? '脱敏合成样张，可用于产品库/RAG/自动插图测试。' : '公开来源素材，正式商用前需复核许可和署名要求。'}</Descriptions.Item>
            </Descriptions>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
