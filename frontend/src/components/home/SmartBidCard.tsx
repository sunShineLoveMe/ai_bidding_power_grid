import { Button } from 'antd';
import { ClipboardList, FileText, UploadCloud } from 'lucide-react';

interface SmartBidCardProps {
  onPrimaryAction: () => void;
  onTechnicalAction: () => void;
  onBusinessAction: () => void;
}

export function SmartBidCard({ onPrimaryAction, onTechnicalAction, onBusinessAction }: SmartBidCardProps): JSX.Element {
  return (
    <section className="grid min-h-32 grid-cols-[430px_1fr] items-center gap-5 rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-soft max-[1500px]:grid-cols-1">
      <div className="flex items-center gap-4">
        <div className="grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-violet-400 to-indigo-600 text-3xl font-black text-white shadow-lg shadow-indigo-200">
          AI
        </div>
        <div>
          <h2 className="mb-1 text-2xl font-black text-indigo-600">智能标书</h2>
          <p className="m-0 text-sm font-semibold leading-6 text-slate-500">
            上传招标文件后，系统会解析招标要求，并按技术标、商务标、资格文件和报价文件生成可编辑初稿。
          </p>
        </div>
      </div>
      <div className="grid grid-cols-[1.2fr_1fr_1fr] gap-3 max-[1500px]:grid-cols-3">
        <Button size="large" type="primary" icon={<UploadCloud size={18} />} onClick={onPrimaryAction}>
          上传招标文件生成标书
        </Button>
        <Button
          size="large"
          icon={<ClipboardList size={18} />}
          onClick={onTechnicalAction}
        >
          继续历史标书
        </Button>
        <Button
          size="large"
          icon={<FileText size={18} />}
          onClick={onBusinessAction}
        >
          管理知识资料
        </Button>
      </div>
    </section>
  );
}
