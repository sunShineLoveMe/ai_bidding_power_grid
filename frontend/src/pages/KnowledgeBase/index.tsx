import { Button, Descriptions, Empty, Modal, Progress, Space, Table, Tag, Upload, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { BookOpen, Database, FileText, RefreshCw, UploadCloud } from 'lucide-react';
import { useState, useEffect, useMemo } from 'react';
import { CategoryList } from '../../components/common/CategoryList';
import { MetricCards } from '../../components/common/MetricCards';
import { ModuleHeader } from '../../components/common/ModuleHeader';
import dayjs from 'dayjs';
import { apiClient } from '../../api/client';

interface KnowledgeFile {
  id: string;
  title: string;
  category: string;
  source_type: string;
  status: 'indexed' | 'processing' | 'failed';
  created_at: string;
}

interface KnowledgeChunk {
  id: string;
  chunk_index: number;
  content: string;
  metadata?: Record<string, unknown>;
}

interface KnowledgeDetail {
  document: KnowledgeFile & {
    bucket?: string;
    object_path?: string;
  };
  chunks: KnowledgeChunk[];
}

const categoryLabel: Record<string, string> = {
  general: '通用资料',
  water_tender_documents: '水利招标文件',
  water_policy_regulations: '水利政策法规',
  water_standards_specs: '水利标准规范',
  water_standard_phrases: '水利标准话术',
  water_capability_library: '水利能力资料',
  water_company_profiles: '企业画像资料',
  water_product_library: '水利产品资料',
  water_qualification_library: '企业资信资料',
  water_upload_workflow: '上传流程样例',
};

const statusColor: Record<string, string> = {
  indexed: 'green',
  processing: 'blue',
  failed: 'red',
};

const statusLabel: Record<string, string> = {
  indexed: '已索引',
  processing: '解析中',
  failed: '解析失败',
};

export function KnowledgeBasePage(): JSX.Element {
  const [activeCategory, setActiveCategory] = useState('全部资料');
  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState<KnowledgeDetail | null>(null);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const { data } = await apiClient.get<KnowledgeFile[]>('/api/knowledge/documents', {
        skipGlobalLoading: true,
      });
      setFiles(data);
    } catch (err) {
      console.error(err);
      message.error("获取知识库列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
    // Poll every 5 seconds if there are processing items
    const interval = setInterval(() => {
      setFiles(currentFiles => {
        if (currentFiles.some(f => f.status === 'processing')) {
          fetchDocuments();
        }
        return currentFiles;
      });
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleUpload = async (options: any) => {
    const { file, onSuccess, onError } = options;
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/knowledge/upload', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error('上传失败');
      message.success('文件上传成功，正在后台解析...');
      onSuccess?.();
      fetchDocuments();
    } catch (err: any) {
      onError?.(err);
      message.error(err.message || '上传出现错误');
    }
  };

  const categories = useMemo(() => {
    const counts = files.reduce<Record<string, number>>((acc, file) => {
      acc[file.category] = (acc[file.category] || 0) + 1;
      return acc;
    }, {});
    return [
      { name: '全部资料', count: files.length },
      ...Object.entries(counts)
        .sort(([a], [b]) => (categoryLabel[a] || a).localeCompare(categoryLabel[b] || b, 'zh-CN'))
        .map(([category, count]) => ({
          name: category,
          label: categoryLabel[category] || category,
          count,
        })),
    ];
  }, [files]);

  const dataSource = activeCategory === '全部资料' ? files : files.filter(file => file.category === activeCategory);

  const handleView = async (record: KnowledgeFile) => {
    try {
      setDetailVisible(true);
      setDetailLoading(true);
      setDetail(null);
      const { data } = await apiClient.get<KnowledgeDetail>(`/api/knowledge/documents/${record.id}`, {
        skipGlobalLoading: true,
      });
      setDetail(data);
    } catch (error: any) {
      message.error(error.message || '获取文档详情失败');
      setDetailVisible(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const columns: ColumnsType<KnowledgeFile> = [
    { title: '文件名称', dataIndex: 'title', ellipsis: true },
    { title: '分类', dataIndex: 'category', width: 140, render: value => <Tag color="blue">{categoryLabel[value] || value}</Tag> },
    { title: '类型', dataIndex: 'source_type', width: 88, render: value => value?.toUpperCase() },
    { title: '索引状态', dataIndex: 'status', width: 100, render: status => <Tag color={statusColor[status] || 'default'}>{statusLabel[status] || status}</Tag> },
    { title: '更新时间', dataIndex: 'created_at', width: 160, render: val => dayjs(val).format('YYYY-MM-DD HH:mm') },
    {
      title: '操作',
      width: 130,
      render: (_, record) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => handleView(record)}>查看</Button>
        </Space>
      ),
    },
  ];

  return (
    <div className="module-shell relative">
      <ModuleHeader
        title="企业知识库"
        description="管理企业介绍、历史标书、项目案例、标准话术和行业资料，为 RAG 标书生成提供可检索知识来源。"
        actions={
          <>
            <Button icon={<RefreshCw size={16} />} onClick={fetchDocuments}>刷新状态</Button>
            <Upload showUploadList={false} customRequest={handleUpload}>
              <Button type="primary" icon={<UploadCloud size={16} />}>上传资料</Button>
            </Upload>
          </>
        }
      />
      <MetricCards
        items={[
          { title: '资料总数', value: files.length, desc: '已上传文档', icon: BookOpen, colorClass: 'bg-blue-50 text-blue-600' },
          { title: '已索引文件', value: files.filter(f => f.status === 'indexed').length, desc: '可用于检索', icon: Database, colorClass: 'bg-emerald-50 text-emerald-600' },
          { title: '解析中任务', value: files.filter(f => f.status === 'processing').length, desc: 'MinerU后台提取中', icon: FileText, colorClass: 'bg-violet-50 text-violet-600' },
          { title: '处理失败', value: files.filter(f => f.status === 'failed').length, desc: '需重新上传', icon: RefreshCw, colorClass: 'bg-orange-50 text-orange-500' },
        ]}
      />
      <div className="grid min-h-0 grid-cols-[240px_minmax(0,1fr)] gap-4">
        <CategoryList title="资料分类" items={categories} activeName={activeCategory} onChange={setActiveCategory} />
        <section className="panel-card flex h-full min-h-0 flex-col overflow-hidden">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="panel-title mb-0">文件列表</h2>
            <div className="flex min-w-0 items-center gap-3 text-xs font-bold text-slate-500">
              <span>索引完成率 {files.length > 0 ? Math.round((files.filter(f => f.status === 'indexed').length / files.length) * 100) : 0}%</span>
              <Progress className="w-36" percent={files.length > 0 ? Math.round((files.filter(f => f.status === 'indexed').length / files.length) * 100) : 0} showInfo={false} size="small" />
            </div>
          </div>
          <div className="mb-3 grid gap-3 text-sm font-semibold text-slate-600 xl:grid-cols-2">
            <div className="rounded-xl bg-slate-50 p-3 leading-6">
              Supabase PGVector 持久化存储，支持水利法规、招标文件、标准话术和企业资料检索。
            </div>
            <div className="rounded-xl bg-blue-50 p-3 leading-6 text-blue-700">
              上传资质扫描件、产品图片或图文混排资料后，可继续扩展图片召回和标书自动配图能力。
            </div>
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
            scroll={{ y: 'calc(100vh - 500px)' }}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无知识库资料，请上传真实企业资料" /> }}
          />
        </section>
      </div>
      <Modal
        title="知识库文档详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={<Button onClick={() => setDetailVisible(false)}>关闭</Button>}
        width={920}
        loading={detailLoading}
      >
        {detail ? (
          <div className="space-y-4">
            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label="文件名称" span={2}>{detail.document.title}</Descriptions.Item>
              <Descriptions.Item label="分类">
                <Tag color="blue">{categoryLabel[detail.document.category] || detail.document.category}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="类型">{detail.document.source_type?.toUpperCase()}</Descriptions.Item>
              <Descriptions.Item label="索引状态">
                <Tag color={statusColor[detail.document.status] || 'default'}>{statusLabel[detail.document.status] || detail.document.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="更新时间">{dayjs(detail.document.created_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
              {detail.document.object_path && (
                <Descriptions.Item label="存储路径" span={2}>{detail.document.object_path}</Descriptions.Item>
              )}
            </Descriptions>

            <div>
              <h3 className="mb-3 text-base font-bold text-slate-900">解析内容预览</h3>
              <div className="max-h-[420px] space-y-3 overflow-y-auto rounded-xl border border-slate-100 bg-slate-50 p-3">
                {detail.chunks.length > 0 ? detail.chunks.map(chunk => (
                  <div key={chunk.id} className="rounded-lg bg-white p-3 shadow-sm">
                    <div className="mb-2 text-xs font-bold text-blue-600">片段 {chunk.chunk_index + 1}</div>
                    <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-slate-600">
                      {chunk.content}
                    </pre>
                  </div>
                )) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可预览的解析片段" />
                )}
              </div>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
