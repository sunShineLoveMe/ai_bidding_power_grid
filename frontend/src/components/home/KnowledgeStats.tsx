import { message } from 'antd';
import { BookOpen, Box, Clock3, ShieldCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { apiClient } from '../../api/client';

interface KnowledgeFile {
  total: number;
  indexed: number;
  processing: number;
  failed: number;
}

interface KnowledgeAsset {
  total: number;
}

interface HistoryResponse {
  items: Array<{ id: string }>;
}

interface KnowledgeOverviewStats {
  documents: KnowledgeFile;
  assets: {
    qualification: KnowledgeAsset;
    product: KnowledgeAsset;
  };
}

export function KnowledgeStats(): JSX.Element {
  const [knowledgeStats, setKnowledgeStats] = useState<KnowledgeOverviewStats | null>(null);
  const [historyCount, setHistoryCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const [knowledgeRes, historyRes] = await Promise.all([
          apiClient.get<KnowledgeOverviewStats>('/api/knowledge/stats', { skipGlobalLoading: true }),
          apiClient.get<HistoryResponse>('/api/bidding/history?limit=100', { skipGlobalLoading: true }),
        ]);
        setKnowledgeStats(knowledgeRes.data || null);
        setHistoryCount(historyRes.data?.items?.length || 0);
      } catch (error: any) {
        message.error(error.message || '知识库状态加载失败');
      } finally {
        setLoading(false);
      }
    };

    void fetchStats();
  }, []);

  const valueOf = (value: number) => (loading ? '...' : value);
  const documentStats = knowledgeStats?.documents || { total: 0, indexed: 0, processing: 0, failed: 0 };
  const qualificationStats = knowledgeStats?.assets.qualification || { total: 0 };
  const productStats = knowledgeStats?.assets.product || { total: 0 };
  const stats = useMemo(() => [
    {
      title: '企业知识库文件数',
      value: valueOf(documentStats.total),
      desc: loading ? '正在加载知识库状态' : documentStats.indexed ? `${documentStats.indexed} 份已完成索引` : '等待真实资料入库',
      icon: BookOpen,
      color: 'bg-blue-50 text-blue-600',
    },
    {
      title: '企业资信库文件数',
      value: valueOf(qualificationStats.total),
      desc: loading ? '正在加载资信资产' : qualificationStats.total ? '可用于资质材料引用' : '等待上传资信文件',
      icon: ShieldCheck,
      color: 'bg-emerald-50 text-emerald-600',
    },
    {
      title: '企业产品库资料数',
      value: valueOf(productStats.total),
      desc: loading ? '正在加载产品资料' : productStats.total ? '可用于技术响应配图' : '等待维护产品资料',
      icon: Box,
      color: 'bg-orange-50 text-orange-500',
    },
    {
      title: '历史任务数',
      value: valueOf(historyCount),
      desc: loading ? '正在加载历史任务' : historyCount ? '可继续解读或编制' : '上传后自动记录',
      icon: Clock3,
      color: 'bg-violet-50 text-violet-600',
    },
  ], [documentStats.indexed, documentStats.total, historyCount, loading, productStats.total, qualificationStats.total]);

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
