import { message } from 'antd';
import { BookOpen, Box, Clock3, ShieldCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { apiClient } from '../../api/client';

interface KnowledgeFile {
  id: string;
  status?: string | null;
}

interface KnowledgeAsset {
  id: string;
}

interface HistoryResponse {
  items: Array<{ id: string }>;
}

export function KnowledgeStats(): JSX.Element {
  const [knowledgeFiles, setKnowledgeFiles] = useState<KnowledgeFile[]>([]);
  const [qualificationAssets, setQualificationAssets] = useState<KnowledgeAsset[]>([]);
  const [productAssets, setProductAssets] = useState<KnowledgeAsset[]>([]);
  const [historyCount, setHistoryCount] = useState(0);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [docsRes, qualificationsRes, productsRes, historyRes] = await Promise.all([
          apiClient.get<KnowledgeFile[]>('/api/knowledge/documents', { skipGlobalLoading: true }),
          apiClient.get<KnowledgeAsset[]>('/api/knowledge/assets?asset_type=qualification_image', { skipGlobalLoading: true }),
          apiClient.get<KnowledgeAsset[]>('/api/knowledge/assets?asset_type=product_image', { skipGlobalLoading: true }),
          apiClient.get<HistoryResponse>('/api/bidding/history?limit=100', { skipGlobalLoading: true }),
        ]);
        setKnowledgeFiles(docsRes.data || []);
        setQualificationAssets(qualificationsRes.data || []);
        setProductAssets(productsRes.data || []);
        setHistoryCount(historyRes.data?.items?.length || 0);
      } catch (error: any) {
        message.error(error.message || '知识库状态加载失败');
      }
    };

    void fetchStats();
  }, []);

  const indexedCount = knowledgeFiles.filter(item => item.status === 'indexed').length;
  const stats = useMemo(() => [
    {
      title: '企业知识库文件数',
      value: knowledgeFiles.length,
      desc: indexedCount ? `${indexedCount} 份已完成索引` : '等待真实资料入库',
      icon: BookOpen,
      color: 'bg-blue-50 text-blue-600',
    },
    {
      title: '企业资信库文件数',
      value: qualificationAssets.length,
      desc: qualificationAssets.length ? '可用于资质材料引用' : '等待上传资信文件',
      icon: ShieldCheck,
      color: 'bg-emerald-50 text-emerald-600',
    },
    {
      title: '企业产品库资料数',
      value: productAssets.length,
      desc: productAssets.length ? '可用于技术响应配图' : '等待维护产品资料',
      icon: Box,
      color: 'bg-orange-50 text-orange-500',
    },
    {
      title: '历史任务数',
      value: historyCount,
      desc: historyCount ? '可继续解读或编制' : '上传后自动记录',
      icon: Clock3,
      color: 'bg-violet-50 text-violet-600',
    },
  ], [historyCount, indexedCount, knowledgeFiles.length, productAssets.length, qualificationAssets.length]);

  return (
    <section className="panel-card">
      <div className="mb-3">
        <h2 className="panel-title mb-1">数据准备情况</h2>
        <p className="m-0 text-xs font-semibold text-slate-500">这些资料会被标书生成和知识库助手调用，数量越完整，生成质量越稳定。</p>
      </div>
      <div className="grid grid-cols-4 gap-3 max-[1500px]:grid-cols-2">
        {stats.map(item => {
          const Icon = item.icon;
          return (
            <article key={item.title} className="flex min-h-28 items-center gap-4 rounded-xl border border-slate-100 bg-white px-4 py-4 shadow-[0_6px_14px_rgba(23,42,88,0.035)]">
              <div className={`grid h-12 w-12 shrink-0 place-items-center rounded-full ${item.color}`}>
                <Icon size={22} />
              </div>
              <div className="min-w-0">
                <small className="block truncate text-xs font-bold text-slate-500">{item.title}</small>
                <strong className="my-1 block text-2xl leading-none text-slate-950">{item.value}</strong>
                <small className="block truncate text-xs font-semibold text-slate-500">{item.desc}</small>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
