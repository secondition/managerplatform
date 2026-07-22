import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  hint?: string;
  className?: string;
}

// Neutral empty/placeholder box shared by empty lists and disabled features.
export default function EmptyState({ icon, title, hint, className = '' }: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed border-zinc-200 bg-zinc-50/40 py-8 px-4 text-center ${className}`}
    >
      {icon && <div className="text-zinc-300">{icon}</div>}
      <p className="text-xs font-medium text-zinc-500">{title}</p>
      {hint && <p className="text-[11px] text-zinc-400">{hint}</p>}
    </div>
  );
}
