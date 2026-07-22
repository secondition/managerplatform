import { useState } from 'react';
import { Sparkles, Lightbulb, Check, X, RefreshCw, AlertTriangle, CircleCheck, HelpCircle } from 'lucide-react';
import { dayjs } from '@/lib/date';
import type { AiStatus, DailyScoreOut, WeeklyScoreOut } from '@/types/api';
import {
  useDailyScore,
  useGenerateDailyScore,
  useWeeklyScore,
  useGenerateWeeklyScore,
  useSuggestions,
  useGenerateSuggestions,
  useAcceptSuggestion,
  useRejectSuggestion,
} from './aiHooks';
import { useOkrMonth } from '@/features/okr/hooks';

// AI daily score + today's suggestions. When the provider is not configured the
// backend returns status "not_enabled" and we keep a friendly empty state — the
// buttons still exist so the flow is discoverable once an admin wires up a key.

function NotEnabled({ hint }: { hint: string }) {
  return (
    <div className="flex min-h-[3.625rem] items-center gap-3 border-t border-slate-100 px-5 text-xs text-slate-500"><Sparkles size={16} className="text-slate-300" /><span><b className="mr-2 font-medium text-slate-600">AI 尚未启用</b>{hint}</span></div>
  );
}

function errText(err: unknown): string {
  return err instanceof Error ? err.message : 'AI 生成失败，请稍后再试';
}

// 今日建议 — sits directly under the date picker, above the task list.
export function TodaySuggestion({ date }: { date: string }) {
  const query = useSuggestions(date);
  const generate = useGenerateSuggestions(date);
  const accept = useAcceptSuggestion(date);
  const reject = useRejectSuggestion(date);

  const data = generate.data ?? query.data;
  const status: AiStatus = data?.status ?? 'empty';
  const items = (data?.items ?? []).filter((s) => s.status === 'pending');
  const busy = generate.isPending;

  return (
    <div className="workspace-card overflow-hidden">
      <div className="flex h-[3.25rem] items-center justify-between px-5">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-zinc-900"><Lightbulb size={16} className="theme-icon-color" />今日建议</h3>
        <button
          onClick={() => generate.mutate(undefined)}
          disabled={busy}
          className="flex cursor-pointer items-center gap-1.5 text-xs text-[var(--theme-accent)] transition-colors hover:opacity-80 disabled:opacity-40"
        >
          <RefreshCw size={12} className={busy ? 'animate-spin' : ''} />
          {busy ? '生成中…' : '重新建议'}
        </button>
      </div>

      {generate.isError && <p className="border-t border-slate-100 px-5 py-2 text-[11px] text-red-500">{errText(generate.error)}</p>}

      {status === 'not_enabled' ? (
        <NotEnabled hint="接入 AI 后将结合当日事项与卡点给出优先级建议。" />
      ) : items.length === 0 ? (
        <div className="flex min-h-[3.625rem] items-center gap-3 border-t border-slate-100 px-5 text-xs text-slate-500"><Lightbulb size={16} className="text-slate-300" /><span><b className="mr-2 font-medium text-slate-600">暂无今日建议</b>点「重新建议」，AI 会结合当日事项与 OKR 给出优先级建议。</span></div>
      ) : (
        <div>
          <ul>
            {items.map((s) => (
              <li
                key={s.id}
                className="flex min-h-[2.5625rem] items-center gap-3 border-t border-slate-100 px-5 py-1.5"
              >
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${SUGGESTION_TYPE_STYLE[s.suggestion_type]}`}
                >
                  {SUGGESTION_TYPE_LABEL[s.suggestion_type] ?? '建议'}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-zinc-800">{s.content}</p>
                  {s.needs_info && s.ask.question && (
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] text-blue-700">{s.ask.question}</span>
                        {(s.ask.options ?? []).map((option) => (
                          <button
                            key={option}
                            onClick={() => generate.mutate(`${s.content}：${option}`)}
                            disabled={busy}
                            className="cursor-pointer rounded-full border border-[var(--theme-accent)] bg-white px-2 py-0.5 text-[10px] text-[var(--theme-accent)] hover:bg-[var(--theme-accent-soft)] disabled:opacity-40"
                          >
                            {option}
                          </button>
                        ))}
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {!s.needs_info && (
                    <button
                      onClick={() => accept.mutate(s.id)}
                      disabled={accept.isPending}
                      title="加入今日清单"
                      className="flex h-7 cursor-pointer items-center gap-1 rounded-md bg-[var(--theme-accent)] px-3 text-xs font-medium text-white shadow-sm transition-colors hover:bg-[var(--theme-accent-hover)] disabled:opacity-40"
                    >
                      <Check size={13} />确认
                    </button>
                  )}
                  <button
                    onClick={() => reject.mutate(s.id)}
                    disabled={reject.isPending}
                    title="删除建议"
                    className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-800 disabled:opacity-40 cursor-pointer transition-colors"
                  >
                    <X size={13} />取消
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

    </div>
  );
}

const SUGGESTION_TYPE_LABEL: Record<string, string> = {
  red: '预警',
  amber: '推进',
  blue: '协作',
  green: '建议',
};

const SUGGESTION_TYPE_STYLE: Record<string, string> = {
  red: 'bg-red-100 text-red-700',
  amber: 'bg-amber-100 text-amber-700',
  blue: 'bg-blue-100 text-blue-700',
  green: 'bg-emerald-100 text-emerald-700',
};

const LEVEL_COLOR: Record<string, string> = {
  优秀: 'text-emerald-600',
  达标: 'text-blue-600',
  待改进: 'text-amber-600',
};

// AI 日报评分 — sits at the very bottom.
export function AiScorePanel({ date }: { date: string }) {
  const [tab, setTab] = useState<'today' | 'yesterday' | 'week' | 'okr'>('today');
  const yesterday = dayjs(date).subtract(1, 'day').format('YYYY-MM-DD');
  const todayQuery = useDailyScore(date);
  const yesterdayQuery = useDailyScore(yesterday);
  const weeklyQuery = useWeeklyScore(date);
  const generateToday = useGenerateDailyScore(date);
  const generateWeekly = useGenerateWeeklyScore(date);
  const okrMonth = useOkrMonth(dayjs(date).format('YYYY-MM'));

  const todayData = todayQuery.data;
  const yesterdayData = yesterdayQuery.data;
  const weeklyData = weeklyQuery.data;
  const okrReview = okrMonth.data?.review;
  const okrScore = okrReview?.status === 'ready' ? okrReview.quality_score : null;
  const tabs = [
    { key: 'today' as const, label: '今日得分' },
    { key: 'yesterday' as const, label: '昨日得分' },
    { key: 'week' as const, label: '上周得分' },
    { key: 'okr' as const, label: '本月OKR点评' },
  ];
  const selectedData = tab === 'today' ? todayData : tab === 'yesterday' ? yesterdayData : tab === 'week' ? weeklyData : undefined;
  const selectedReady = selectedData?.status === 'ready';
  const selectedBusy = tab === 'today' ? generateToday.isPending : tab === 'week' ? generateWeekly.isPending : false;
  const selectedGenerate = tab === 'today' ? () => generateToday.mutate() : tab === 'week' ? () => generateWeekly.mutate() : undefined;

  const statusMessage = tab === 'today'
    ? selectedReady
      ? `今日 AI 评分 ${todayData?.total_score ?? '--'} 分，${todayData?.level ?? '已生成'}。`
      : '今日暂无 AI 评分。系统每天 17:00、23:50 自动生成；你也可以现在手动生成。'
    : tab === 'yesterday'
      ? selectedReady
        ? `昨日 AI 评分 ${yesterdayData?.total_score ?? '--'} 分，${yesterdayData?.level ?? '已生成'}。`
        : '昨日暂无 AI 评分。'
      : tab === 'week'
        ? selectedReady
          ? `上周综合评分 ${weeklyData?.total_score ?? '--'} 分，统计周期：${weeklyRange(weeklyData)}。`
          : '上周暂无 AI 综合评分。你可以现在手动生成。'
        : okrScore != null
          ? `本月 OKR 点评 ${okrScore} 分${okrReview?.summary ? `：${okrReview.summary}` : '。'}`
          : '本月暂无 OKR 点评。';

  return (
    <div>
      <div className="flex h-[2.375rem] items-end border-b border-slate-200">
        <div className="flex h-full items-end gap-2">
          {tabs.map((item) => (
            <button key={item.key} onClick={() => setTab(item.key)} className={`relative flex h-full items-center px-3 text-xs after:absolute after:inset-x-1 after:bottom-1 after:h-0.5 ${tab === item.key ? 'font-semibold text-[var(--theme-accent)] after:bg-[var(--theme-accent)]' : 'text-slate-600 after:bg-transparent hover:text-slate-900'}`}>
              {item.label}
              {item.key === 'okr' && okrScore != null && <span className="ml-2 text-[10px] font-normal text-slate-400"><b className="text-blue-500">{okrScore}</b>{okrReview?.summary ? `·${okrReview.summary}` : ''}</span>}
            </button>
          ))}
        </div>
        <HelpCircle size={14} className="mb-3 ml-auto text-slate-300" />
      </div>

      {(generateToday.isError || generateWeekly.isError) && (
        <p className="mt-2 text-[11px] text-red-500">
          {errText(generateToday.error ?? generateWeekly.error)}
        </p>
      )}

      <div className="mt-3 flex min-h-[3.375rem] items-center gap-2 rounded-[14px] border border-blue-200 bg-blue-50/70 px-4 text-xs text-[#315b8a]">
        <CircleCheck size={16} className="shrink-0 text-emerald-600" />
        <span>{statusMessage}</span>
        {selectedGenerate && !selectedReady && <button onClick={selectedGenerate} disabled={selectedBusy} className="ml-auto h-8 shrink-0 rounded-md border border-[#b8cbe3] bg-white px-3 text-xs font-medium text-[#315b8a] hover:border-[var(--theme-accent)] hover:text-[var(--theme-accent)] disabled:opacity-40">{selectedBusy ? '生成中…' : '立即生成评分'}</button>}
      </div>

      {tab === 'today' && todayData?.status === 'ready' && <div className="workspace-card mt-3 p-5"><DetailTitle>今日评分详情</DetailTitle><ScoreDetail data={todayData} /></div>}
      {tab === 'yesterday' && yesterdayData?.status === 'ready' && <div className="workspace-card mt-3 p-5"><DetailTitle>昨日评分详情</DetailTitle><ScoreDetail data={yesterdayData} /></div>}
      {tab === 'week' && weeklyData?.status === 'ready' && <div className="workspace-card mt-3 p-5"><DetailTitle>上周评分详情</DetailTitle><WeeklyScoreDetail data={weeklyData} /></div>}
    </div>
  );
}

function weeklyRange(data: WeeklyScoreOut | undefined): string {
  if (!data?.week_start || !data.week_end) return '上一完整自然周';
  return `${data.week_start} 至 ${data.week_end}`;
}


function DetailTitle({ children }: { children: string }) {
  return <h4 className="text-[11px] font-semibold text-zinc-500 mb-3">{children}</h4>;
}

function ScoreDetail({ data }: { data: DailyScoreOut }) {
  const levelColor = data.level ? LEVEL_COLOR[data.level] ?? 'text-zinc-600' : 'text-zinc-600';
  return (
    <div className="space-y-4">
      <div className="flex items-end gap-4">
        <div className="flex items-baseline gap-1">
          <span className="text-4xl font-bold text-blue-600 font-mono tabular-nums">
            {data.total_score ?? '--'}
          </span>
          <span className="text-xs text-zinc-400">/ 100</span>
        </div>
        <div className="flex-1 pb-1">
          <div className="flex items-center gap-2">
            {data.level && <span className={`text-xs font-semibold ${levelColor}`}>{data.level}</span>}
            {data.score_delta != null && (
              <span
                className={`text-[11px] font-mono ${
                  data.score_delta >= 0 ? 'text-emerald-600' : 'text-red-500'
                }`}
              >
                {data.score_delta >= 0 ? '+' : ''}
                {data.score_delta}
              </span>
            )}
          </div>
          {data.one_line_review && (
            <p className="text-xs text-zinc-600 mt-0.5">{data.one_line_review}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {data.dimensions.map((d) => (
          <div key={d.name} className="rounded-xl border border-zinc-100 bg-zinc-50/40 p-3">
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] font-semibold text-zinc-500">{d.name}</span>
              <span className="text-sm font-bold text-zinc-800 font-mono tabular-nums">
                {d.score}
                <span className="text-[10px] text-zinc-400">/{d.full}</span>
              </span>
            </div>
            {d.comment && <p className="text-[10px] text-zinc-400 mt-1">{d.comment}</p>}
          </div>
        ))}
      </div>

      {data.trend_note && (
        <p className="text-[11px] text-zinc-500">
          <span className="font-semibold text-zinc-600">趋势：</span>
          {data.trend_note}
        </p>
      )}

      {data.okr_outside_high_value.length > 0 && (
        <div className="text-[11px] text-zinc-500">
          <span className="font-semibold text-zinc-600">OKR 外高价值：</span>
          {data.okr_outside_ratio && (
            <span className="text-zinc-400">（{data.okr_outside_ratio}）</span>
          )}
          {data.okr_outside_high_value.join('、')}
        </div>
      )}

      {data.manager_hint && (
        <p className="text-[11px] text-zinc-500">
          <span className="font-semibold text-zinc-600">管理者提示：</span>
          {data.manager_hint}
        </p>
      )}

      {data.okr_clarity_warning && (
        <div className="flex items-start gap-1.5 rounded-lg bg-amber-50 border border-amber-100 px-3 py-2 text-[11px] text-amber-700">
          <AlertTriangle size={12} className="mt-0.5 shrink-0" />
          <span>{data.okr_clarity_warning}</span>
        </div>
      )}
    </div>
  );
}

function WeeklyScoreDetail({ data }: { data: WeeklyScoreOut }) {
  return (
    <div className="space-y-4">
      {data.summary && <p className="text-xs text-zinc-700">{data.summary}</p>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {data.dimensions.map((dimension) => (
          <div key={dimension.name} className="rounded-xl border border-zinc-100 bg-zinc-50/40 p-3">
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] font-semibold text-zinc-500">{dimension.name}</span>
              <span className="text-sm font-bold text-zinc-800 font-mono tabular-nums">
                {dimension.score}
                <span className="text-[10px] text-zinc-400">/{dimension.full}</span>
              </span>
            </div>
            {dimension.comment && (
              <p className="text-[10px] text-zinc-400 mt-1">{dimension.comment}</p>
            )}
          </div>
        ))}
      </div>

      {data.key_achievements.length > 0 && (
        <p className="text-[11px] text-zinc-500">
          <span className="font-semibold text-zinc-600">关键产出：</span>
          {data.key_achievements.join('、')}
        </p>
      )}
      {data.concerns.length > 0 && (
        <p className="text-[11px] text-amber-700">
          <span className="font-semibold">需关注：</span>
          {data.concerns.join('、')}
        </p>
      )}
      {data.manager_hint && (
        <p className="text-[11px] text-zinc-500">
          <span className="font-semibold text-zinc-600">管理者提示：</span>
          {data.manager_hint}
        </p>
      )}
    </div>
  );
}
