import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { AlertCircle, Check, PanelLeftClose, PanelLeftOpen, Search, UserMinus, UserPlus, ChevronLeft, ChevronRight, Target, Gauge, FileText } from 'lucide-react';
import { dayjs, toApiMonth, type Dayjs } from '@/lib/date';
import { toNum } from '@/lib/num';
import Spinner from '@/components/ui/Spinner';
import UserProfileLink from '@/components/user/UserProfileLink';
import type { KeyResultOut, MonthlyReportSectionOut, ObjectiveOut } from '@/types/api';
import {
  useOkrSubscriptionCandidates,
  useOkrSubscriptions,
  useSubscribeOkr,
  useSubscribedOkrMonth,
  useUnsubscribeOkr,
} from './hooks';

function pct(value: unknown): number {
  const n = toNum(value);
  if (n === null) return 0;
  return Math.max(0, Math.min(100, Math.round(n)));
}

export default function OkrSubscriptionPage() {
  const location = useLocation();
  // A profile score card can navigate here with a target user to pre-select.
  const initialUserId =
    (location.state as { subscriptionUserId?: number } | null)?.subscriptionUserId ?? null;
  const [month, setMonth] = useState<Dayjs>(dayjs().startOf('month'));
  const [selectedUserId, setSelectedUserId] = useState<number | null>(initialUserId);
  const [q, setQ] = useState('');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarMode, setSidebarMode] = useState<'people' | 'add'>('people');

  const monthStr = toApiMonth(month);
  const subscriptions = useOkrSubscriptions();
  const candidates = useOkrSubscriptionCandidates(q);
  const subscribe = useSubscribeOkr();
  const unsubscribe = useUnsubscribeOkr();
  const okr = useSubscribedOkrMonth(selectedUserId, monthStr);

  const subscribedUsers = subscriptions.data ?? [];
  const selectedSubscription = subscribedUsers.find((item) => item.target_user.id === selectedUserId);

  useEffect(() => {
    if (selectedUserId !== null) return;
    const first = subscribedUsers[0]?.target_user.id;
    if (first) setSelectedUserId(first);
  }, [selectedUserId, subscribedUsers]);

  useEffect(() => {
    if (selectedUserId === null) return;
    if (subscriptions.isSuccess && !subscribedUsers.some((item) => item.target_user.id === selectedUserId)) {
      setSelectedUserId(subscribedUsers[0]?.target_user.id ?? null);
    }
  }, [selectedUserId, subscribedUsers, subscriptions.isSuccess]);

  const objectives = okr.data?.objectives ?? [];
  const avgProgress =
    objectives.length > 0
      ? Math.round(objectives.reduce((sum, o) => sum + (toNum(o.progress) ?? 0), 0) / objectives.length)
      : 0;

  return (
    <div className="space-y-6 max-w-[1320px] w-full mx-auto px-4 md:px-8 py-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-zinc-900">订阅 OKR</h2>
          <p className="text-xs text-zinc-400 mt-1">订阅同事即可查看其日报与 OKR，此处展示月度 OKR 与月报。订阅视图只读，不会获得编辑权限。</p>
        </div>
        <MonthPager month={month} onChange={setMonth} />
      </div>

      <div className={`grid grid-cols-1 items-start ${sidebarCollapsed ? '' : 'lg:grid-cols-[320px_minmax(0,1fr)]'} gap-6`}>
        <aside className="contents">
          {!sidebarCollapsed && <section className="lg:col-start-1 lg:row-start-1 rounded-xl border border-zinc-200 bg-white p-4 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
            <div className="mb-3 flex items-center gap-2">
              <div className="flex flex-1 rounded-lg bg-zinc-100 p-0.5">
                <button type="button" onClick={() => setSidebarMode('people')} className={`flex-1 rounded-md px-2.5 py-1.5 text-[11px] transition-colors ${sidebarMode === 'people' ? 'bg-white font-semibold text-[var(--theme-accent)] shadow-sm' : 'text-zinc-500 hover:text-zinc-700'}`}>我订阅的人</button>
                <button type="button" onClick={() => setSidebarMode('add')} className={`flex-1 rounded-md px-2.5 py-1.5 text-[11px] transition-colors ${sidebarMode === 'add' ? 'bg-white font-semibold text-[var(--theme-accent)] shadow-sm' : 'text-zinc-500 hover:text-zinc-700'}`}>添加订阅</button>
              </div>
              <button type="button" onClick={() => setSidebarCollapsed(true)} className="rounded p-1 text-zinc-300 hover:bg-zinc-50 hover:text-zinc-600" title="收起订阅侧边栏" aria-label="收起订阅侧边栏"><PanelLeftClose size={14} /></button>
            </div>

            {sidebarMode === 'people' ? (
              subscriptions.isLoading ? (
                <Spinner label="加载订阅…" />
              ) : subscribedUsers.length === 0 ? (
                <div className="text-xs text-zinc-400 border border-dashed border-zinc-200 rounded-xl py-6 px-3 text-center">
                  还没有订阅同事，切换到「添加订阅」搜索添加。
                </div>
              ) : (
                <div className="flex max-h-[280px] flex-col gap-1.5 overflow-y-auto pr-1">
                  {subscribedUsers.map((item) => (
                    <div
                      key={item.id}
                      onClick={() => setSelectedUserId(item.target_user.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setSelectedUserId(item.target_user.id);
                        }
                      }}
                      role="button"
                      tabIndex={0}
                      className={`flex items-center justify-between gap-2 rounded-xl px-3 py-2 cursor-pointer transition-colors ${
                        item.target_user.id === selectedUserId ? 'bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]' : 'hover:bg-zinc-50'
                      }`}
                    >
                      <UserProfileLink
                        user={item.target_user}
                        size={24}
                        nameClassName="text-xs font-medium text-zinc-700 truncate"
                        className="max-w-[220px]"
                        onClick={(e) => e.stopPropagation()}
                      />
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); unsubscribe.mutate(item.target_user.id); }}
                        disabled={unsubscribe.isPending}
                        className="inline-flex items-center gap-1 text-[10px] text-zinc-400 hover:text-red-600 disabled:opacity-40 cursor-pointer"
                        title="取消订阅"
                      >
                        <UserMinus size={12} />
                        取消
                      </button>
                    </div>
                  ))}
                </div>
              )
            ) : (
              <>
                <div className="flex items-center gap-2 bg-zinc-50 rounded-xl px-3 py-2 mb-3">
                  <Search size={13} className="text-zinc-400" />
                  <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="搜索同事"
                    className="bg-transparent outline-none text-xs flex-1 text-zinc-700"
                  />
                </div>
                <div className="max-h-[280px] overflow-y-auto space-y-1.5 pr-1">
                  {(candidates.data ?? []).map((item) => (
                    <div key={item.user.id} className="flex items-center justify-between gap-2 rounded-xl px-3 py-2 hover:bg-zinc-50">
                      <UserProfileLink user={item.user} size={24} nameClassName="text-xs font-medium text-zinc-700 truncate" />
                      {item.subscribed ? (
                        <span className="inline-flex items-center gap-1 text-[10px] text-emerald-600">
                          <Check size={12} />
                          已订阅
                        </span>
                      ) : (
                        <button
                          onClick={() => subscribe.mutate(item.user.id)}
                          disabled={subscribe.isPending}
                          className="inline-flex items-center gap-1 text-[10px] text-[var(--theme-accent)] hover:text-[var(--theme-accent-hover)] disabled:opacity-40 cursor-pointer"
                        >
                          <UserPlus size={12} />
                          订阅
                        </button>
                      )}
                    </div>
                  ))}
                  {candidates.isLoading && <Spinner label="搜索中…" />}
                  {!candidates.isLoading && (candidates.data ?? []).length === 0 && (
                    <div className="text-center py-5 text-xs text-zinc-400 border border-dashed border-zinc-200 rounded-xl">
                      没有可订阅员工。
                    </div>
                  )}
                </div>
              </>
            )}
          </section>}
        </aside>

        <main className="space-y-4">
          {sidebarCollapsed && <button type="button" onClick={() => setSidebarCollapsed(false)} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-2.5 text-[11px] text-zinc-500 shadow-sm hover:border-[var(--theme-accent)] hover:text-[var(--theme-accent)]" title="展开订阅侧边栏"><PanelLeftOpen size={13} />订阅管理</button>}
          {selectedUserId === null ? (
            <EmptyPanel title="选择一位同事" desc="订阅同事后，可以在这里按月查看 TA 的 OKR 与月报。" />
          ) : okr.isLoading ? (
            <Spinner label="正在加载订阅 OKR…" />
          ) : okr.isError ? (
            <div className="flex items-center gap-2 rounded-2xl bg-red-50 border border-red-100 px-4 py-3 text-xs text-red-600">
              <AlertCircle size={14} />
              加载订阅 OKR 失败，请确认订阅关系仍然有效。
            </div>
          ) : (
            <>
              <div className="bg-white rounded-2xl border border-zinc-200 p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex items-center gap-3">
                {(okr.data?.target_user ?? selectedSubscription?.target_user) && (
                  <UserProfileLink
                    user={(okr.data?.target_user ?? selectedSubscription?.target_user)!}
                    size={34}
                    nameClassName="text-sm font-bold text-zinc-900 truncate"
                    className="gap-3"
                  />
                )}
                <p className="text-[11px] text-zinc-400 font-mono">{monthStr}</p>
              </div>

              {objectives.length === 0 ? (
                <EmptyPanel title="本月暂无 OKR" desc="对方这个月还没有设定目标。" />
              ) : (
                <>
                  <div className="bg-white rounded-2xl border border-zinc-200 p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex items-center justify-between gap-4">
                    <div className="flex items-center gap-2.5">
                      <span className="p-1.5 bg-[var(--theme-accent-soft)] text-[var(--theme-icon-color)] rounded-lg">
                        <Gauge size={14} />
                      </span>
                      <div>
                        <p className="text-xs font-semibold text-zinc-700">本月 OKR 均分</p>
                        <p className="text-[11px] text-zinc-400">共 {objectives.length} 个目标，按目标进度平均</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 min-w-[180px]">
                      <div className="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                        <div className="h-full bg-[var(--theme-accent)] rounded-full transition-all" style={{ width: `${avgProgress}%` }} />
                      </div>
                      <span className="text-xl font-bold text-[var(--theme-accent)] font-mono tabular-nums w-14 text-right">
                        {avgProgress}%
                      </span>
                    </div>
                  </div>

                  {objectives.map((obj, index) => (
                    <ReadonlyObjective key={obj.id} index={index + 1} objective={obj} />
                  ))}
                </>
              )}

              {(okr.data?.monthly_report.length ?? 0) > 0 && (
                <ReadonlyMonthlyReport
                  sections={okr.data?.monthly_report ?? []}
                  monthLabel={month.format('YYYY年M月')}
                />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function MonthPager({ month, onChange }: { month: Dayjs; onChange: (m: Dayjs) => void }) {
  const isCurrent = toApiMonth(month) === toApiMonth(dayjs());
  return (
    <div className="flex items-center gap-1 bg-white rounded-xl border border-zinc-200 p-1 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <button
        onClick={() => onChange(month.subtract(1, 'month'))}
        className="p-1.5 rounded-lg text-zinc-500 hover:bg-zinc-50 hover:text-[var(--theme-accent)] cursor-pointer transition-colors"
        title="上一月"
      >
        <ChevronLeft size={14} />
      </button>
      <span className="px-2 text-xs font-mono font-semibold text-zinc-700 tabular-nums">{month.format('YYYY-MM')}</span>
      <button
        onClick={() => onChange(month.add(1, 'month'))}
        disabled={isCurrent}
        className="p-1.5 rounded-lg text-zinc-500 hover:bg-zinc-50 hover:text-[var(--theme-accent)] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
        title="下一月"
      >
        <ChevronRight size={14} />
      </button>
      {!isCurrent && (
        <button
          onClick={() => onChange(dayjs().startOf('month'))}
          className="ml-1 px-2 py-1 rounded-lg text-[11px] text-[var(--theme-accent)] hover:bg-[var(--theme-accent-soft)] cursor-pointer transition-colors"
        >
          回到本月
        </button>
      )}
    </div>
  );
}

function ReadonlyObjective({ index, objective }: { index: number; objective: ObjectiveOut }) {
  const progress = pct(objective.progress);
  return (
    <div className="bg-white rounded-2xl border border-zinc-200 p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] space-y-4">
      <div className="flex items-start gap-2">
        <span className="p-1.5 bg-[var(--theme-accent-soft)] text-[var(--theme-icon-color)] rounded-lg shrink-0">
          <Target size={13} /> O{index}
        </span>
        <div className="min-w-0">
          <h3 className="text-sm font-bold text-zinc-900 leading-snug">{objective.title}</h3>
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-zinc-400">目标进度</span>
          <span className="font-mono font-semibold text-[var(--theme-accent)] tabular-nums">{progress}%</span>
        </div>
        <div className="h-1.5 bg-zinc-100 rounded-full overflow-hidden">
          <div className="h-full bg-[var(--theme-accent)] rounded-full transition-all" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <div className="space-y-2">
        {objective.key_results.map((kr, index) => (
          <ReadonlyKeyResult key={kr.id} index={index + 1} kr={kr} />
        ))}
      </div>
    </div>
  );
}

function ReadonlyKeyResult({ index, kr }: { index: number; kr: KeyResultOut }) {
  const progress = pct(kr.progress);
  return (
    <div className="rounded-xl border border-zinc-100 bg-zinc-50/30 px-3 py-2.5">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-zinc-800 truncate">KR{index} {kr.title}</span>
      </div>
      <div className="flex items-center gap-3 mt-2">
        <div className="flex-1 h-1 bg-zinc-200/70 rounded-full overflow-hidden">
          <div className="h-full bg-[var(--theme-accent)] opacity-75 rounded-full transition-all" style={{ width: `${progress}%` }} />
        </div>
        <span className="text-[10px] font-mono text-zinc-400 tabular-nums w-9 text-right">{progress}%</span>
      </div>
    </div>
  );
}

function ReadonlyMonthlyReport({ sections, monthLabel }: { sections: MonthlyReportSectionOut[]; monthLabel: string }) {
  return (
    <div className="bg-white rounded-2xl border border-zinc-200 p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] space-y-4">
      <div className="flex items-center gap-2">
        <span className="p-1.5 bg-[var(--theme-accent-soft)] text-[var(--theme-icon-color)] rounded-lg">
          <FileText size={13} />
        </span>
        <h3 className="text-sm font-bold text-zinc-900">{monthLabel}月报</h3>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sections.map((section) => (
          <div key={section.id} className="rounded-xl border border-zinc-100 bg-zinc-50/20 p-4 space-y-2.5">
            <h4 className="text-xs font-semibold text-zinc-700">{section.title}</h4>
            {section.content_html ? (
              <div
                className="tiptap text-[11px] text-zinc-600 leading-relaxed"
                dangerouslySetInnerHTML={{ __html: section.content_html }}
              />
            ) : (
              <p className="text-[11px] text-zinc-300 italic">暂无内容。</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyPanel({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="bg-white rounded-2xl border border-zinc-200 p-10 shadow-[0_8px_30px_rgb(0,0,0,0.02)] text-center">
      <h3 className="text-sm font-bold text-zinc-800">{title}</h3>
      <p className="text-xs text-zinc-400 mt-2">{desc}</p>
    </div>
  );
}
