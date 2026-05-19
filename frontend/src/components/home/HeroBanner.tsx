import { ArrowRight, BookOpenCheck, FileSearch, FileText } from 'lucide-react';
import { Fragment } from 'react';

export function HeroBanner(): JSX.Element {
  const steps = [
    { title: '上传招标文件', desc: 'PDF / Word', icon: FileSearch },
    { title: 'AI 解读要求', desc: '评分点 / 废标项', icon: BookOpenCheck },
    { title: '生成标书初稿', desc: '章节大纲 / Word', icon: FileText },
  ] as const;

  return (
    <section className="grid min-h-52 grid-cols-[1fr_520px] overflow-hidden rounded-2xl border border-blue-100 bg-[radial-gradient(circle_at_88%_20%,rgba(50,103,255,0.10),transparent_26%),linear-gradient(110deg,#f6fbff_0%,#eaf3ff_72%,#e4efff_100%)] px-10 py-8 shadow-soft max-[1500px]:grid-cols-[1fr_420px]">
      <div className="min-w-0">
        <h1 className="mb-4 text-4xl font-black leading-none tracking-normal text-slate-950">AI 标书工作台</h1>
        <div className="mb-4 flex flex-wrap items-center gap-4 text-xl font-black text-blue-600">
          <span>企业单机部署版</span>
          <span>·</span>
          <span>本地知识库驱动</span>
          <span>·</span>
          <span>分章节生成</span>
          <span>·</span>
          <span>Word 导出</span>
        </div>
        <p className="max-w-3xl text-base font-semibold leading-7 text-slate-500">
          帮助企业快速完成资料入库、招标解析、标书生成与导出，适合非技术人员直接使用。
        </p>
      </div>
      <div className="self-center rounded-2xl border border-white/80 bg-white/70 p-4 shadow-[0_18px_50px_rgba(50,103,255,0.12)] backdrop-blur">
        <div className="mb-4 flex items-center gap-3">
          <img className="h-11 w-11 rounded-xl object-contain" src="/assets/brand-logo.png" alt="AI标书系统" />
          <div>
            <strong className="block text-base text-slate-950">一站式标书编制流程</strong>
            <span className="text-xs font-bold text-slate-500">从招标文件到可编辑初稿</span>
          </div>
        </div>
        <div className="grid grid-cols-[1fr_24px_1fr_24px_1fr] items-stretch gap-2">
          {steps.map((step, index) => {
            const Icon = step.icon;
            return (
              <Fragment key={step.title}>
                <div className="rounded-xl border border-blue-100 bg-white px-3 py-4">
                  <div className="mb-3 grid h-9 w-9 place-items-center rounded-lg bg-blue-50 text-blue-600">
                    <Icon size={18} />
                  </div>
                  <strong className="block text-sm text-slate-900">{step.title}</strong>
                  <span className="mt-1 block text-xs font-semibold text-slate-500">{step.desc}</span>
                </div>
                {index < steps.length - 1 ? (
                  <div key={`${step.title}-arrow`} className="grid place-items-center text-blue-500">
                    <ArrowRight size={18} />
                  </div>
                ) : null}
              </Fragment>
            );
          })}
        </div>
      </div>
    </section>
  );
}
