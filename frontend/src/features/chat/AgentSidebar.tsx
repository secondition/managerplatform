import { Bot, ChevronDown, Sparkles } from 'lucide-react';
import type { ChatAgentSummary } from './types';

interface AgentNavigationProps {
  agents: ChatAgentSummary[];
  selectedAgentKey: string | null;
  onSelect: (agentKey: string) => void;
}

export function AgentSidebar({ agents, selectedAgentKey, onSelect }: AgentNavigationProps) {
  return (
    <aside className="hidden min-h-0 w-[252px] shrink-0 flex-col border-r border-slate-200/80 bg-slate-50/55 md:flex">
      <div className="border-b border-slate-200/80 px-4 py-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <Sparkles size={15} className="text-[var(--theme-icon-color)]" />
          我的智能体
        </div>
        <p className="mt-1 text-[11px] leading-5 text-slate-400">仅展示当前账号已开放的智能体</p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {agents.length > 0 ? (
          <div className="space-y-1.5">
            {agents.map((agent) => {
              const selected = agent.agent_key === selectedAgentKey;
              return (
                <button
                  key={agent.agent_key}
                  type="button"
                  onClick={() => onSelect(agent.agent_key)}
                  className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left ${
                    selected
                      ? 'border-[var(--theme-accent)] bg-[var(--theme-accent-soft)]'
                      : 'border-transparent hover:border-slate-200 hover:bg-white'
                  }`}
                >
                  <AgentAvatar agent={agent} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5">
                      <strong className={`min-w-0 flex-1 truncate text-[12px] ${selected ? 'text-[var(--theme-accent)]' : 'text-slate-800'}`}>
                        {agent.name}
                      </strong>
                    </span>
                    <span className="mt-0.5 block truncate text-[10px] text-slate-400">{agent.description}</span>
                  </span>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-white/70 px-4 text-center">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-400">
              <Bot size={18} />
            </span>
            <strong className="mt-3 text-[12px] font-semibold text-slate-600">暂无可用智能体</strong>
            <span className="mt-1 text-[10px] leading-4 text-slate-400">管理员开放智能体后会自动显示在这里</span>
          </div>
        )}
      </div>
    </aside>
  );
}

export function MobileAgentPicker({ agents, selectedAgentKey, onSelect }: AgentNavigationProps) {
  const selectedAgent = agents.find((agent) => agent.agent_key === selectedAgentKey) ?? null;

  return (
    <div className="shrink-0 border-b border-slate-200/80 bg-slate-50/60 p-3 md:hidden">
      {selectedAgent ? (
        <label className="relative flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5">
          <AgentAvatar agent={selectedAgent} />
          <span className="min-w-0 flex-1">
            <span className="block text-[10px] text-slate-400">当前智能体</span>
            <strong className="block truncate text-[12px] text-slate-800">{selectedAgent.name}</strong>
          </span>
          <ChevronDown size={14} className="text-slate-400" />
          <select
            value={selectedAgentKey ?? ''}
            onChange={(event) => onSelect(event.target.value)}
            aria-label="选择智能体"
            className="absolute inset-0 cursor-pointer opacity-0"
          >
            {agents.map((agent) => (
              <option key={agent.agent_key} value={agent.agent_key}>{agent.name}</option>
            ))}
          </select>
        </label>
      ) : (
        <div className="flex items-center gap-2 rounded-xl border border-dashed border-slate-200 bg-white/70 px-3 py-2.5 text-[11px] text-slate-400">
          <Bot size={15} />
          暂无可用智能体
        </div>
      )}
    </div>
  );
}

function AgentAvatar({ agent }: { agent: ChatAgentSummary }) {
  if (agent.avatar_url) {
    return <img src={agent.avatar_url} alt="" className="h-9 w-9 shrink-0 rounded-xl object-cover" />;
  }
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]">
      <Bot size={17} />
    </span>
  );
}
