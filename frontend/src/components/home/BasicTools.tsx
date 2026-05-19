import { AlertTriangle, FileSearch, FileText, ListChecks } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const tools = [
  {
    title: '招标文件解读',
    description: '提取项目基础信息、技术要求、商务要求、评分标准',
    icon: FileSearch,
    color: 'bg-blue-500',
    path: '/interpretation',
    action: '进入解读',
  },
  {
    title: '评分项检查',
    description: '识别评分标准，检查内容覆盖情况',
    icon: ListChecks,
    color: 'bg-emerald-500',
    path: '/interpretation',
    action: '查看评分',
  },
  {
    title: '废标项检查',
    description: '提示强制项与潜在废标风险',
    icon: AlertTriangle,
    color: 'bg-orange-400',
    path: '/interpretation',
    action: '查看风险',
  },
  {
    title: 'Word 导出',
    description: '按固定模板导出可编辑 Word 文档',
    icon: FileText,
    color: 'bg-blue-700',
    path: '/history',
    action: '查看任务',
  },
] as const;

export function BasicTools(): JSX.Element {
  const navigate = useNavigate();

  return (
    <section className="panel-card">
      <div className="mb-3">
        <h2 className="panel-title mb-1">常用功能</h2>
        <p className="m-0 text-xs font-semibold text-slate-500">围绕一次投标任务，按“解读、检查、导出”逐步处理。</p>
      </div>
      <div className="grid grid-cols-4 gap-3 max-[1500px]:grid-cols-2">
        {tools.map(tool => {
          const Icon = tool.icon;
          return (
            <button
              key={tool.title}
              type="button"
              onClick={() => navigate(tool.path)}
              className="flex min-h-44 min-w-0 flex-col items-center justify-center rounded-xl border border-slate-100 bg-white px-4 py-4 text-center shadow-[0_6px_14px_rgba(23,42,88,0.04)] transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-[0_10px_24px_rgba(50,103,255,0.12)]"
            >
              <div className={`mb-3 grid h-11 w-11 place-items-center rounded-xl text-white ${tool.color}`}>
                <Icon size={22} />
              </div>
              <strong className="mb-2 text-sm text-slate-900">{tool.title}</strong>
              <span className="text-xs font-semibold leading-5 text-slate-500">{tool.description}</span>
              <span className="mt-3 text-xs font-black text-blue-600">{tool.action}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
