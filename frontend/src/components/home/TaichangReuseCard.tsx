import { Button } from 'antd';
import { ArrowRight, BookOpenCheck, FileSearch, FileStack, Sparkles } from 'lucide-react';

interface TaichangReuseCardProps {
  onCreate: () => void;
}

const stages = [
  {
    title: '选择招标项目',
    description: '上传本次招标文件，创建泰昌专版投标任务。',
    icon: FileSearch,
  },
  {
    title: '确认目录与要求',
    description: '核对动态目录、固定表单和条件章节变化。',
    icon: BookOpenCheck,
  },
  {
    title: '匹配泰昌资料',
    description: '自动筛选已审核的可用资料，并提示必要缺口。',
    icon: FileStack,
  },
  {
    title: '生成技术／商务标',
    description: '组装正文、表格与附件，生成可编辑投标文件。',
    icon: Sparkles,
  },
] as const;

export function TaichangReuseCard({ onCreate }: TaichangReuseCardProps): JSX.Element {
  return (
    <section className="panel-card overflow-hidden border-indigo-100 bg-[linear-gradient(112deg,#ffffff_0%,#f8faff_60%,#f2f6ff_100%)] px-5 py-5">
      <div className="mb-4 flex items-start justify-between gap-5 max-[1100px]:flex-col">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-indigo-600 px-2 py-1 text-xs font-black text-white">泰昌专版</span>
            <h2 className="m-0 text-xl font-black text-slate-950">泰昌历史标书复用</h2>
          </div>
          <p className="m-0 max-w-4xl text-sm font-semibold leading-6 text-slate-500">
            以本次招标文件为准，结合泰昌已审核资料和历史技术标、商务标的编排经验，快速生成本项目投标初稿。
          </p>
        </div>
        <Button
          className="shrink-0 max-[1100px]:w-full"
          size="large"
          type="primary"
          icon={<ArrowRight size={18} />}
          iconPosition="end"
          onClick={onCreate}
        >
          创建泰昌专版标书
        </Button>
      </div>

      <div className="grid grid-cols-4 gap-3 max-[1200px]:grid-cols-2 max-[760px]:grid-cols-1">
        {stages.map((stage, index) => {
          const Icon = stage.icon;
          return (
            <article key={stage.title} className="min-w-0 rounded-xl border border-slate-100 bg-white/90 px-4 py-3 shadow-[0_4px_12px_rgba(23,42,88,0.035)]">
              <div className="mb-2 flex items-center gap-2">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-indigo-50 font-black text-indigo-600">
                  {index + 1}
                </span>
                <Icon className="shrink-0 text-indigo-500" size={17} aria-hidden="true" />
                <strong className="min-w-0 text-sm text-slate-900">{stage.title}</strong>
              </div>
              <p className="m-0 text-xs font-semibold leading-5 text-slate-500">{stage.description}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
