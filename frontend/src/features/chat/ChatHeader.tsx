import { Bot } from 'lucide-react';
import type { ChatAgentSummary } from './types';

interface ChatHeaderProps {
  agent: ChatAgentSummary | null;
}

export default function ChatHeader({ agent }: ChatHeaderProps) {
  return (
    <header className="flex min-h-[78px] shrink-0 items-center border-b border-slate-200/80 bg-white px-4 py-3 sm:px-5">
      <div className="flex min-w-0 items-center gap-3">
        {agent?.avatar_url ? (
          <img
            src={agent.avatar_url}
            alt={`${agent.name}图标`}
            className="h-10 w-10 shrink-0 rounded-xl object-cover"
          />
        ) : (
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]">
            <Bot size={19} />
          </span>
        )}
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold text-slate-950">{agent?.name ?? 'AI 大脑'}</h2>
          <p className="mt-0.5 truncate text-[11px] text-slate-400">
            {agent?.description ?? '统一、安全的企业智能体工作空间'}
          </p>
        </div>
      </div>
    </header>
  );
}
