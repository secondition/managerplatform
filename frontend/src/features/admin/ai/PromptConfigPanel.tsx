import { useEffect, useState } from 'react';
import { FileText, Loader2, Save, RotateCcw } from 'lucide-react';
import Spinner from '@/components/ui/Spinner';
import type { PromptConfigOut } from '@/types/api';
import { useAiPrompts, useUpdateAiPrompt, useRestoreAiPrompt } from './hooks';

const TYPE_LABELS: Record<string, string> = {
  daily_score: '日报评分',
  weekly_score: '周表现评分',
  daily_suggestion: '今日建议',
  okr_quality: 'OKR 质量评分',
  monthly_report_score: '月报评分',
};

export default function PromptConfigPanel() {
  const prompts = useAiPrompts();
  const update = useUpdateAiPrompt();
  const restore = useRestoreAiPrompt();

  const [activeType, setActiveType] = useState<string>('daily_score');
  const [name, setName] = useState('');
  const [version, setVersion] = useState('');
  const [draft, setDraft] = useState('');
  const [selectedVars, setSelectedVars] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false);

  const list = prompts.data ?? [];
  const active: PromptConfigOut | undefined = list.find((p) => p.prompt_type === activeType);

  // Reset the form whenever the active row changes (tab switch or after save).
  useEffect(() => {
    if (active) {
      setName(active.name);
      setVersion(active.version);
      setDraft(active.template_content);
      setSelectedVars(active.variables);
      setDirty(false);
    }
  }, [active?.id, active?.name, active?.version, active?.template_content, active?.variables]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleVar = (key: string) => {
    setSelectedVars((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
    setDirty(true);
  };

  if (prompts.isLoading) return <Spinner label="加载提示词..." />;

  return (
    <section className="bg-white rounded-2xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="flex items-center gap-2 mb-5">
        <span className="p-1.5 rounded-lg bg-[var(--theme-accent-soft)] text-[var(--theme-icon-color)]">
          <FileText size={15} />
        </span>
        <div>
          <h3 className="text-sm font-bold text-zinc-900">提示词模板</h3>
          <p className="text-xs text-zinc-400 mt-0.5">模板正文只写指令；勾选变量决定哪些数据随提示词发给模型，支持恢复默认。</p>
        </div>
      </div>

      <div className="flex items-center gap-1 bg-zinc-50 rounded-xl p-1 w-fit mb-4">
        {list.map((p) => (
          <button
            key={p.prompt_type}
            onClick={() => setActiveType(p.prompt_type)}
            className={`px-3.5 py-1.5 rounded-lg text-xs cursor-pointer transition-colors ${
              activeType === p.prompt_type
                ? 'bg-white text-[var(--theme-accent)] shadow-sm font-semibold'
                : 'text-zinc-500 hover:text-zinc-700'
            }`}
          >
            {TYPE_LABELS[p.prompt_type] ?? p.prompt_type}
          </button>
        ))}
      </div>

      {active && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_140px] gap-3">
            <label className="block">
              <span className="text-xs font-medium text-zinc-700">模板名称</span>
              <input
                value={name}
                onChange={(e) => {
                  setName(e.target.value.slice(0, 200));
                  setDirty(true);
                }}
                className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-800 outline-none focus:border-[var(--theme-accent)]"
                placeholder="模板名称"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-zinc-700">版本</span>
              <input
                value={version}
                onChange={(e) => {
                  setVersion(e.target.value.slice(0, 50));
                  setDirty(true);
                }}
                className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-800 outline-none focus:border-[var(--theme-accent)]"
                placeholder="如 v1、v2.1"
              />
            </label>
          </div>

          {active.available_variables.length > 0 && (
            <div>
              <span className="text-[11px] text-zinc-500">
                可用变量（勾选后随提示词作为「数据」发送给模型）：
              </span>
              <div className="mt-1.5 grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                {active.available_variables.map((v) => (
                  <label
                    key={v.key}
                    className="flex items-start gap-2 rounded-lg border border-zinc-100 bg-zinc-50/40 px-2.5 py-2 cursor-pointer hover:border-[var(--theme-accent)]"
                  >
                    <input
                      type="checkbox"
                      checked={selectedVars.includes(v.key)}
                      onChange={() => toggleVar(v.key)}
                      className="mt-0.5 w-4 h-4 rounded border-zinc-300 accent-[var(--theme-accent)] cursor-pointer"
                    />
                    <span>
                      <span className="block text-xs font-medium text-zinc-700">{v.label}</span>
                      <span className="block text-[10px] text-zinc-400">{v.description}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <textarea
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              setDirty(true);
            }}
            rows={16}
            className="w-full rounded-xl border border-zinc-200 bg-zinc-50/40 px-3 py-2 text-xs font-mono leading-relaxed text-zinc-800 outline-none focus:border-[var(--theme-accent)]"
          />

          <div className="flex items-center gap-3">
            <button
              onClick={() =>
                update.mutate({
                  promptType: active.prompt_type,
                  input: {
                    name: name.trim(),
                    version: version.trim(),
                    template_content: draft,
                    variables: selectedVars,
                  },
                })
              }
              disabled={!dirty || update.isPending}
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--theme-accent)] px-4 py-2 text-xs font-semibold text-white hover:bg-[var(--theme-accent-hover)] disabled:opacity-50 cursor-pointer"
            >
              {update.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              保存模板
            </button>
            <button
              onClick={() => restore.mutate(active.prompt_type)}
              disabled={restore.isPending}
              className="inline-flex items-center gap-2 rounded-xl border border-zinc-200 px-4 py-2 text-xs font-semibold text-zinc-700 hover:border-[var(--theme-accent)] hover:text-[var(--theme-accent)] disabled:opacity-50 cursor-pointer"
            >
              {restore.isPending ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
              恢复默认
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
