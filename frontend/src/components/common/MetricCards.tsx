import { Tooltip } from 'antd';
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

export interface MetricItem {
  title: string;
  value: string | number;
  desc: string;
  icon: LucideIcon;
  colorClass: string;
  tooltip?: ReactNode;
}

interface MetricCardsProps {
  items: MetricItem[];
}

export function MetricCards({ items }: MetricCardsProps): JSX.Element {
  const gridClass = items.length >= 5 ? 'grid-cols-5' : 'grid-cols-4';
  return (
    <div className={`grid h-24 ${gridClass} gap-3`}>
      {items.map(item => {
        const Icon = item.icon;
        const iconNode = (
          <div className={`grid h-12 w-12 shrink-0 place-items-center rounded-full ${item.colorClass} ${item.tooltip ? 'cursor-help' : ''}`}>
            <Icon size={22} />
          </div>
        );
        return (
          <article key={item.title} className="flex min-w-0 items-center gap-4 rounded-2xl border border-slate-200 bg-white px-4 shadow-soft">
            {item.tooltip ? (
              <Tooltip title={item.tooltip} placement="top" overlayStyle={{ maxWidth: 360 }}>
                {iconNode}
              </Tooltip>
            ) : iconNode}
            <div className="min-w-0">
              <small className="block truncate text-xs font-bold text-slate-500">{item.title}</small>
              <strong className="my-1 block text-2xl leading-none text-slate-950">{item.value}</strong>
              <small className="block truncate text-xs font-semibold text-slate-500">{item.desc}</small>
            </div>
          </article>
        );
      })}
    </div>
  );
}
