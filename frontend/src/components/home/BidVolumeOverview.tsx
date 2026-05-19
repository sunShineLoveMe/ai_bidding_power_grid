import { Button, Tag } from 'antd';
import { BriefcaseBusiness, ClipboardCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import type { BidSection, InterpretationResponse } from '../../types/interpretation';

type DeliveryVolumeType = 'technical' | 'business';
type InternalVolumeType = 'technical' | 'business' | 'qualification' | 'price' | 'attachment' | 'other';

const volumes: Array<{
  type: DeliveryVolumeType;
  name: string;
  desc: string;
  icon: typeof ClipboardCheck;
  color: string;
}> = [
  { type: 'technical', name: '技术标', desc: '施工组织设计、技术响应、质量安全环保', icon: ClipboardCheck, color: 'blue' },
  { type: 'business', name: '商务标', desc: '投标函、资格资料、报价文件、承诺函和附件材料', icon: BriefcaseBusiness, color: 'purple' },
];

function internalSectionVolume(section: BidSection): InternalVolumeType {
  const metadata = section.metadata || {};
  const volumeType = String(metadata.volume_type || '') as InternalVolumeType;
  if (['technical', 'business', 'qualification', 'price', 'attachment', 'other'].includes(volumeType)) return volumeType;
  const text = `${section.title || ''} ${section.purpose || ''}`;
  if (/报价|清单|价格|单价|工程量/.test(text)) return 'price';
  if (/技术|施工组织|实施方案|质量|安全|环保|进度|设备|工艺/.test(text)) return 'technical';
  if (/资格|资质|证书|营业执照|人员|项目经理|业绩|信誉/.test(text)) return 'qualification';
  if (/商务|合同|付款|履约|服务|偏离|承诺|投标函|授权|保证金/.test(text)) return 'business';
  if (/附件|图纸|扫描件|证明材料|图片|图册/.test(text)) return 'attachment';
  return 'other';
}

function deliverySectionVolume(section: BidSection): DeliveryVolumeType {
  return internalSectionVolume(section) === 'technical' ? 'technical' : 'business';
}

function isGenerated(section: BidSection): boolean {
  return ['generated', 'edited', 'completed'].includes(section.status || '') && !!(section.content || '').trim();
}

export function BidVolumeOverview(): JSX.Element {
  const navigate = useNavigate();
  const [projectId, setProjectId] = useState('');
  const [sections, setSections] = useState<BidSection[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await apiClient.get<InterpretationResponse>('/api/bidding/interpretations/latest', {
          skipGlobalLoading: true,
        });
        setProjectId(data.project?.id || '');
        setSections(data.sections || []);
      } catch {
        setProjectId('');
        setSections([]);
      }
    };
    void load();
  }, []);

  const stats = useMemo(() => volumes.map(volume => {
    const scoped = sections.filter(section => deliverySectionVolume(section) === volume.type);
    const done = scoped.filter(isGenerated).length;
    const failed = scoped.filter(section => section.status === 'failed').length;
    return {
      ...volume,
      total: scoped.length,
      done,
      failed,
    };
  }), [sections]);

  return (
    <section className="panel-card bid-volume-overview">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <h2 className="panel-title mb-1">标书分册工作区</h2>
          <p className="m-0 text-xs font-semibold text-slate-500">上传一次招标文件后，系统按真实投标习惯组织为技术标和商务标；资格、报价、附件作为商务标内部资料管理。</p>
        </div>
        <Button disabled={!projectId} onClick={() => navigate(projectId ? `/bid-editor?projectId=${projectId}` : '/history')}>
          进入分册编制
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-3 max-[900px]:grid-cols-1">
        {stats.map(item => {
          const Icon = item.icon;
          const status = item.total ? (item.failed ? '有风险' : item.done === item.total ? '已完成' : '编写中') : '待生成';
          return (
            <article key={item.type} className="rounded-xl border border-slate-100 bg-white px-4 py-4 shadow-[0_6px_14px_rgba(23,42,88,0.035)]">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-blue-50 text-blue-600">
                    <Icon size={18} />
                  </span>
                  <strong className="truncate text-base text-slate-950">{item.name}</strong>
                </div>
                <Tag color={item.failed ? 'red' : item.done && item.done === item.total ? 'green' : item.total ? 'blue' : 'default'}>{status}</Tag>
              </div>
              <p className="m-0 min-h-10 text-xs font-semibold leading-5 text-slate-500">{item.desc}</p>
              <div className="mt-3 flex items-center justify-between text-xs font-bold text-slate-500">
                <span>章节 {item.total}</span>
                <span>完成 {item.done}</span>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
