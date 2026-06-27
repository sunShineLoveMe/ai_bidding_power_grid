export interface CategoryItem {
  name: string;
  label?: string;
  count: number;
}

interface CategoryListProps {
  title: string;
  items: CategoryItem[];
  activeName: string;
  onChange: (name: string) => void;
}

export function CategoryList({ title, items, activeName, onChange }: CategoryListProps): JSX.Element {
  return (
    <section className="panel-card flex h-full min-h-0 flex-col">
      <h2 className="panel-title">{title}</h2>
      <div className="grid min-h-0 gap-2 overflow-y-auto pr-1">
        {items.map(item => {
          const active = item.name === activeName;
          return (
            <button
              key={item.name}
              type="button"
              className={`flex h-11 items-center justify-between rounded-xl px-3 text-sm font-bold transition ${
                active ? 'bg-blue-50 text-blue-600' : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
              }`}
              onClick={() => onChange(item.name)}
            >
              <span className="min-w-0 truncate pr-2">{item.label || item.name}</span>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-extrabold leading-5 ${
                  active ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'
                }`}
              >
                {item.count > 99 ? '99+' : item.count}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
