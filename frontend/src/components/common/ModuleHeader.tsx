import type { ReactNode } from 'react';

interface ModuleHeaderProps {
  title: string;
  description: string;
  actions?: ReactNode;
}

export function ModuleHeader({ title, description, actions }: ModuleHeaderProps): JSX.Element {
  return (
    <section className="flex h-24 items-center justify-between rounded-2xl border border-blue-100 bg-[linear-gradient(110deg,#f8fbff_0%,#eef5ff_100%)] px-7 shadow-soft">
      <div className="min-w-0">
        <h1 className="m-0 text-3xl font-black leading-tight text-slate-950">{title}</h1>
        <p className="mt-2 max-w-3xl truncate text-sm font-semibold text-slate-500">{description}</p>
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-3">{actions}</div> : null}
    </section>
  );
}
