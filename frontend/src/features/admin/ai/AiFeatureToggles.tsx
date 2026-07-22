import { ToggleRight } from 'lucide-react';
import Spinner from '@/components/ui/Spinner';
import type { AiFeatureFlagsOut } from '@/types/api';
import { useAiFeatures, useUpdateAiFeatures } from './hooks';

const TOGGLES: { key: keyof AiFeatureFlagsOut; label: string; hint: string }[] = [
  { key: 'daily_score_enabled', label: '日报评分', hint: '允许生成日报 AI 评分' },
  { key: 'daily_suggestion_enabled', label: '今日建议', hint: '允许生成今日建议' },
  { key: 'okr_review_enabled', label: 'OKR 点评', hint: '允许生成 OKR 月度质量评分' },
  {
    key: 'scheduler_enabled',
    label: '定时任务',
    hint: '每天 17:00 / 23:50 自动评分，月末自动 OKR 点评',
  },
];

export default function AiFeatureToggles() {
  const features = useAiFeatures();
  const update = useUpdateAiFeatures();

  if (features.isLoading) return <Spinner label="加载功能开关..." />;
  const data = features.data;
  if (!data) return null;

  return (
    <section className="bg-white rounded-2xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="flex items-center gap-2 mb-5">
        <span className="p-1.5 rounded-lg bg-[var(--theme-accent-soft)] text-[var(--theme-icon-color)]">
          <ToggleRight size={15} />
        </span>
        <div>
          <h3 className="text-sm font-bold text-zinc-900">评分功能开关</h3>
          <p className="text-xs text-zinc-400 mt-0.5">分别控制各项评分、建议与后台定时生成。</p>
        </div>
      </div>

      <div className="space-y-3 max-w-xl">
        {TOGGLES.map((t) => (
          <label
            key={t.key}
            className="flex items-center justify-between gap-3 rounded-xl border border-zinc-100 bg-zinc-50/40 px-4 py-3 cursor-pointer"
          >
            <div className="min-w-0">
              <div className="text-xs font-semibold text-zinc-800">{t.label}</div>
              <p className="text-[11px] text-zinc-400 mt-0.5">{t.hint}</p>
            </div>
            <input
              type="checkbox"
              checked={Boolean(data[t.key])}
              disabled={update.isPending}
              onChange={(e) => update.mutate({ [t.key]: e.target.checked })}
              className="h-4 w-4 rounded border-zinc-300 accent-[var(--theme-accent)] focus:ring-[var(--theme-accent-ring)]"
            />
          </label>
        ))}
      </div>
    </section>
  );
}
