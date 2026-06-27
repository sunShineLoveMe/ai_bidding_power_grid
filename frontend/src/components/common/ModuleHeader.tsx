import type { ReactNode } from 'react';

interface ModuleHeaderProps {
  title: string;
  description: string;
  actions?: ReactNode;
}

export function ModuleHeader({ title, description, actions }: ModuleHeaderProps): JSX.Element {
  return (
    <section className="flex min-h-24 flex-wrap items-center justify-between gap-4 rounded-2xl border border-blue-100 bg-[linear-gradient(110deg,#f8fbff_0%,#eef5ff_100%)] px-7 py-5 shadow-soft">
      <div className="min-w-0">
        <h1 className="m-0 break-words text-3xl font-black leading-tight text-slate-950">{title}</h1>
        <p className="mt-2 max-w-3xl break-words text-sm font-semibold leading-5 text-slate-500">{description}</p>
      </div>
      {actions ? <div className="flex min-w-0 shrink-0 flex-wrap items-center justify-end gap-3">{actions}</div> : null}
    </section>
  );
}
