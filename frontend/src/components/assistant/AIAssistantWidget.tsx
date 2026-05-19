import { FormEvent, useState } from 'react';
import { Bot, Send, X } from 'lucide-react';
import { Button, Input } from 'antd';
import { useAssistantStore } from '../../stores/assistantStore';

const quickQuestions = ['如何开始生成标书？', '企业知识库怎么用？', '什么是评分项检查？', '如何导出 Word？'];

function reply(question: string): string {
  if (question.includes('开始') || question.includes('生成')) {
    return '先选择并上传招标文件，然后依次执行 AI 预分析、提取章节格式、生成章节设计，最后生成 Word。';
  }
  if (question.includes('知识库')) {
    return '企业知识库用于保存公司介绍、历史标书、项目案例、制度模板和行业资料。生成正文时系统会检索相关内容作为参考。';
  }
  if (question.includes('评分')) {
    return '评分项检查用于识别招标文件中的评分标准，并提醒投标正文是否覆盖关键得分点。';
  }
  if (question.includes('Word') || question.includes('导出')) {
    return '完成章节设计后点击“生成 Word”，系统会生成可下载的 Word 文件。';
  }
  return '第一版助手主要解答系统使用、资料入库和生成流程问题。建议先完善企业知识库、资信库、产品库，再上传招标文件生成标书。';
}

export function AIAssistantWidget(): JSX.Element {
  const [input, setInput] = useState('');
  const { open, messages, setOpen, addMessage } = useAssistantStore();

  function ask(question: string): void {
    const value = question.trim();
    if (!value) return;
    addMessage({ role: 'user', content: value });
    window.setTimeout(() => addMessage({ role: 'assistant', content: reply(value) }), 160);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    ask(input);
    setInput('');
  }

  return (
    <>
      <Button
        className="fixed bottom-[68px] right-7 z-40 h-12 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 px-7 text-base font-black shadow-lg shadow-indigo-200"
        type="primary"
        icon={<Bot size={19} />}
        onClick={() => setOpen(!open)}
      >
        AI 助手
      </Button>

      {open ? (
        <section className="fixed bottom-32 right-7 z-40 grid h-[500px] w-[360px] grid-rows-[64px_1fr_58px] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-panel">
          <header className="flex items-center justify-between border-b border-slate-100 px-4">
            <div className="flex items-center gap-3">
              <div className="grid h-9 w-9 place-items-center rounded-xl bg-blue-50 text-blue-600">
                <Bot size={20} />
              </div>
              <div>
                <strong className="block text-slate-950">AI 标书助手</strong>
                <small className="font-bold text-emerald-500">● 在线</small>
              </div>
            </div>
            <Button type="text" icon={<X size={18} />} onClick={() => setOpen(false)} />
          </header>

          <div className="flex min-h-0 flex-col gap-3 overflow-hidden bg-slate-50 p-4">
            <div className="grid grid-cols-2 gap-2">
              {quickQuestions.map(question => (
                <button
                  key={question}
                  type="button"
                  className="min-h-8 rounded-lg bg-blue-50 px-2 text-xs font-bold text-blue-600"
                  onClick={() => ask(question)}
                >
                  {question}
                </button>
              ))}
            </div>
            <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
              {messages.slice(-6).map(message => (
                <div
                  key={message.id}
                  className={`max-w-[86%] rounded-2xl px-3 py-2 text-xs font-semibold leading-5 ${
                    message.role === 'user' ? 'self-end bg-blue-100 text-slate-700' : 'self-start bg-white text-slate-600'
                  }`}
                >
                  {message.content}
                </div>
              ))}
            </div>
          </div>

          <form className="grid grid-cols-[1fr_42px] gap-2 border-t border-slate-100 p-2.5" onSubmit={handleSubmit}>
            <Input value={input} placeholder="请输入问题..." onChange={event => setInput(event.target.value)} />
            <Button htmlType="submit" type="primary" icon={<Send size={16} />} />
          </form>
        </section>
      ) : null}
    </>
  );
}
