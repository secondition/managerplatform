import { useState } from 'react';
import { Check, ChevronRight, RefreshCw, Sparkles } from 'lucide-react';
import { toNum } from '@/lib/num';
import type { AiStatus } from '@/types/api';
import { useOkrReview, useGenerateOkrReview } from './hooks';

export default function OkrReviewCard({ month }: { month: string }) {
  const [showDimensions, setShowDimensions] = useState(false);
  const query = useOkrReview(month);
  const generate = useGenerateOkrReview(month);
  const data = generate.data ?? query.data;
  const status: AiStatus = data?.status ?? 'empty';
  const ready = status === 'ready' && Boolean(data);
  const quality = toNum(data?.total_score ?? null);

  return (
    <section className="workspace-card p-5 text-[12px]">
      <div className="flex min-h-[116px] flex-col items-center justify-center rounded-xl bg-[var(--theme-accent-soft)] px-4 text-center">
        <p className="text-[11px] font-medium text-[var(--theme-accent)]">本月 OKR（{month}）</p>
        <div className="mt-1 flex items-baseline gap-1">
          <strong className="text-[40px] font-semibold leading-10 text-slate-950 tabular-nums">{ready && quality !== null ? quality : '--'}</strong>
          <span className="text-[11px] text-slate-400">/100</span>
        </div>
        <p className={`mt-0.5 text-[11px] font-semibold ${ready ? 'text-emerald-600' : 'text-slate-400'}`}>{ready ? (data?.level ?? '已生成') : status === 'not_enabled' ? 'AI 尚未启用' : '等待生成点评'}</p>
      </div>

      <div className="mt-6 flex items-center gap-2">
        <Sparkles size={14} className="text-[var(--theme-icon-color)]" />
        <h2 className="text-[13px] font-semibold leading-5 text-slate-950">本月OKR点评</h2>
        <span className="text-[11px] text-slate-400">评的是写得好不好，不是完成度</span>
      </div>

      {generate.isError && <p className="mt-3 text-xs text-red-500">{generate.error instanceof Error ? generate.error.message : 'AI 生成失败，请稍后再试'}</p>}

      {!ready ? (
        <div className="mt-3 flex min-h-[58px] items-center justify-between gap-4 rounded-lg bg-slate-50 px-4 text-xs text-slate-500">
          <span>{status === 'not_enabled' ? '请联系管理员配置评分服务后生成点评。' : 'AI 将评估本月整套 OKR 的方向价值、KR 支撑度和事务饱和度。'}</span>
          {status !== 'not_enabled' && <button onClick={() => generate.mutate()} disabled={generate.isPending} className="workspace-button workspace-button-primary h-8 shrink-0 disabled:opacity-40"><RefreshCw size={12} className={generate.isPending ? 'animate-spin' : ''} />{generate.isPending ? '生成中…' : '生成点评'}</button>}
        </div>
      ) : (
        <>
          {data?.summary && <p className="mt-2.5 rounded-lg bg-slate-50 px-3 py-2 text-[12px] leading-5 text-slate-700">{data.summary}</p>}

          {data && data.highlights.length > 0 && (
            <div className="mt-2.5 flex items-start gap-1.5 text-[12px] leading-5 text-slate-600">
              <Check size={14} className="mt-0.5 shrink-0 text-emerald-600" />
              <p><b className="mr-1 text-emerald-700">做得好的地方</b>{data.highlights.join('；')}</p>
            </div>
          )}

          {data && data.optional_improvements.length > 0 && (
            <div className="mt-2.5 rounded-lg border border-[var(--theme-accent-ring)] bg-[var(--theme-accent-soft)] p-3 text-[12px] leading-5">
              <h3 className="mb-1 font-semibold text-[var(--theme-accent)]">建议优化（锦上添花）</h3>
              <div className="space-y-2 text-slate-600">
                {data.optional_improvements.map((item, index) => (
                  <div key={`${item.target}-${index}`}>
                    <p><span className="text-slate-400">[{item.target}]</span> <span className="text-slate-700">{item.point}</span></p>
                    <p className="pl-3 text-slate-500">→ {item.suggestion}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data?.impact_on_daily_scoring && <p className="mt-2.5 text-[12px] leading-5 text-slate-500"><span className="mr-1 text-slate-400">日报评分影响：</span>{data.impact_on_daily_scoring}</p>}

          {showDimensions && data && data.dimensions.length > 0 && (
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
              {data.dimensions.map((dimension) => (
                <div key={dimension.name} className="rounded-lg border border-slate-100 bg-slate-50/60 p-3">
                  <div className="flex items-center justify-between gap-2"><span className="text-xs font-medium text-slate-700">{dimension.name}</span><b className="text-xs text-[var(--theme-accent)]">{dimension.score}/{dimension.full}</b></div>
                  {dimension.comment && <p className="mt-1 text-[11px] leading-4 text-slate-400">{dimension.comment}</p>}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <div className="mt-5 flex items-center justify-between">
        <button onClick={() => setShowDimensions((value) => !value)} disabled={!ready || !data?.dimensions.length} className="flex items-center gap-1 text-[11px] text-[var(--theme-accent)] disabled:text-slate-300">{showDimensions ? '收起评分维度' : '查看评分维度'}<ChevronRight size={12} className={showDimensions ? 'rotate-90' : ''} /></button>
        <button onClick={() => generate.mutate()} disabled={generate.isPending || status === 'not_enabled'} className="flex items-center gap-1 text-[11px] text-slate-600 hover:text-[var(--theme-accent)] disabled:text-slate-300"><RefreshCw size={12} className={generate.isPending ? 'animate-spin' : ''} />{generate.isPending ? '生成中…' : ready ? '重新生成' : '生成点评'}</button>
      </div>
    </section>
  );
}
