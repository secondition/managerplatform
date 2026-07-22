import { AlertTriangle, RefreshCw, Sparkles, WandSparkles } from 'lucide-react';
import type { AiStatus } from '@/types/api';
import {
  useGenerateMonthlyReportScore,
  useMonthlyReportScore,
} from './hooks';

export default function MonthlyReportScoreCard({ month }: { month: string }) {
  const query = useMonthlyReportScore(month);
  const generate = useGenerateMonthlyReportScore(month);
  const data = generate.data ?? query.data;
  const status: AiStatus = data?.status ?? 'empty';
  const busy = generate.isPending;

  return (
    <div className="border-t border-zinc-100 pt-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-xs font-bold text-zinc-900 flex items-center gap-1.5">
          <span className="p-1 bg-violet-50 text-violet-600 rounded-md">
            <Sparkles size={12} />
          </span>
          AI 月报评分
        </h4>
        <button
          onClick={() => generate.mutate()}
          disabled={busy}
          className="flex items-center gap-1 text-[11px] text-[var(--theme-accent)] hover:text-[var(--theme-accent-hover)] disabled:opacity-40 cursor-pointer"
        >
          <RefreshCw size={12} className={busy ? 'animate-spin' : ''} />
          {busy ? '评分中…' : status === 'ready' ? '重新评分' : '生成评分'}
        </button>
      </div>

      {generate.isError && (
        <p className="text-[11px] text-red-500">
          {generate.error instanceof Error ? generate.error.message : 'AI 评分失败，请稍后重试'}
        </p>
      )}

      {status === 'not_enabled' ? (
        <p className="text-xs text-zinc-400">AI 尚未启用，请联系管理员配置 Provider。</p>
      ) : status !== 'ready' || !data ? (
        <p className="text-xs text-zinc-400">
          AI 将结合整月日报、问题方案、OKR 进度和本页月报栏目，评估汇报质量。
        </p>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-violet-600 font-mono tabular-nums">
                {data.total_score ?? '--'}
              </span>
              <span className="text-xs text-zinc-400">/ 100</span>
            </div>
            {data.summary && <p className="flex-1 text-xs text-zinc-600">{data.summary}</p>}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2">
            {data.dimensions.map((dimension) => (
              <div key={dimension.name} className="rounded-xl border border-zinc-100 bg-zinc-50/40 p-3">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[11px] font-semibold text-zinc-600">{dimension.name}</span>
                  <span className="text-xs font-bold text-violet-600 font-mono">
                    {dimension.score}/{dimension.full}
                  </span>
                </div>
                {dimension.comment && (
                  <p className="text-[10px] text-zinc-400 mt-1">{dimension.comment}</p>
                )}
              </div>
            ))}
          </div>

          {data.doubts.length > 0 && (
            <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-3">
              <p className="text-[11px] font-semibold text-amber-700 flex items-center gap-1 mb-1">
                <AlertTriangle size={12} /> 存疑点（仅供核对）
              </p>
              {data.doubts.map((doubt) => (
                <p key={doubt} className="text-[11px] text-amber-800">· {doubt}</p>
              ))}
            </div>
          )}

          <div className="rounded-xl border border-[var(--theme-accent-ring)] bg-[var(--theme-accent-soft)] p-3">
            <p className="text-[11px] font-semibold text-[var(--theme-accent)] flex items-center gap-1 mb-1">
              <WandSparkles size={12} /> 下月可执行建议
            </p>
            {data.suggestions.map((suggestion) => (
              <p key={suggestion} className="text-[11px] text-zinc-700">· {suggestion}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
