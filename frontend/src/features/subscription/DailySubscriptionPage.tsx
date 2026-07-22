import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { AlertCircle, Check, PanelLeftClose, PanelLeftOpen, Search, UserMinus, UserPlus } from 'lucide-react';
import { dayjs, type Dayjs, toApiDate } from '@/lib/date';
import DateWeekPicker from '@/components/date/DateWeekPicker';
import Spinner from '@/components/ui/Spinner';
import UserProfileLink from '@/components/user/UserProfileLink';
import type { DailyTaskOut, ProblemSolutionOut } from '@/types/api';
import {
  useDailySubscriptionCandidates,
  useDailySubscriptions,
  useSubscribeDaily,
  useSubscribedDailyReport,
  useUnsubscribeDaily,
} from './hooks';

const REPEAT_LABEL = {
  none: '今日',
  daily: '每日',
  weekly: '每周',
} as const;

export default function DailySubscriptionPage() {
  const location = useLocation();
  // A profile score card can navigate here with a target user to pre-select.
  const initialUserId =
    (location.state as { subscriptionUserId?: number } | null)?.subscriptionUserId ?? null;
  const [selectedDate, setSelectedDate] = useState<Dayjs>(() => dayjs());
  const date = toApiDate(selectedDate);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(initialUserId);
  const [q, setQ] = useState('');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarMode, setSidebarMode] = useState<'people' | 'add'>('people');

  const subscriptions = useDailySubscriptions();
  const candidates = useDailySubscriptionCandidates(q);
  const subscribe = useSubscribeDaily();
  const unsubscribe = useUnsubscribeDaily();
  const report = useSubscribedDailyReport(selectedUserId, date);

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

  return (
    <div className="space-y-6 max-w-[1320px] w-full mx-auto px-4 md:px-8 py-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-zinc-900">订阅日报</h2>
          <p className="text-xs text-zinc-400 mt-1">订阅同事即可查看其日报与 OKR，此处展示日报内容。订阅视图只读，不会获得编辑或完成权限。</p>
        </div>
        <div className="md:min-w-[460px]">
          <DateWeekPicker selected={selectedDate} onSelect={setSelectedDate} hideExtras />
        </div>
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
            <EmptyPanel title="选择一位同事" desc="订阅同事后，可以在这里按日期查看 TA 的日报。" />
          ) : report.isLoading ? (
            <Spinner label="正在加载订阅日报…" />
          ) : report.isError ? (
            <div className="flex items-center gap-2 rounded-2xl bg-red-50 border border-red-100 px-4 py-3 text-xs text-red-600">
              <AlertCircle size={14} />
              加载订阅日报失败，请确认订阅关系仍然有效。
            </div>
          ) : (
            <>
              <div className="bg-white rounded-2xl border border-zinc-200 p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex items-center gap-3">
                {(report.data?.target_user ?? selectedSubscription?.target_user) && (
                  <UserProfileLink
                    user={(report.data?.target_user ?? selectedSubscription?.target_user)!}
                    size={34}
                    nameClassName="text-sm font-bold text-zinc-900 truncate"
                    className="gap-3"
                  />
                )}
                <p className="text-[11px] text-zinc-400">{date}</p>
              </div>

              {(report.data?.tasks.length ?? 0) === 0 && (report.data?.problems.length ?? 0) === 0 ? (
                <EmptyPanel title="当天暂无日报" desc="对方这一天还没有记录工作事项或问题。" />
              ) : (
                <>
                  <ReadonlyTaskList tasks={report.data?.tasks ?? []} />
                  <ReadonlyProblemList problems={report.data?.problems ?? []} />
                </>
              )}
            </>
          )}
        </main>
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

function ReadonlyTaskList({ tasks }: { tasks: DailyTaskOut[] }) {
  const completed = tasks.filter((t) => t.is_done).length;
  return (
    <section className="bg-white rounded-2xl border border-zinc-200 p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-zinc-900">工作清单</h3>
        <span className="text-[11px] text-zinc-400 font-mono">已完成 {completed} / {tasks.length}</span>
      </div>
      <div className="space-y-1.5">
        {tasks.map((task) => (
          <div key={task.id} className="flex items-center gap-3 rounded-xl px-3 py-2.5 bg-zinc-50/40">
            <span className={`w-4 h-4 rounded border shrink-0 ${task.is_done ? 'bg-[var(--theme-accent)] border-[var(--theme-accent)]' : 'border-zinc-300'}`} />
            <span className="font-mono text-[11px] text-zinc-400 shrink-0 w-11">{task.task_time.slice(0, 5)}</span>
            <div className="flex-1 min-w-0">
              <span className={`text-xs ${task.is_done ? 'line-through text-zinc-400' : 'text-zinc-800'}`}>
                {task.content}
              </span>
              <div className="flex flex-wrap items-center gap-1.5 mt-1">
                {task.repeat_rule !== 'none' && (
                  <span className="text-[10px] text-violet-600 bg-violet-50 rounded px-1.5 py-0.5">
                    {REPEAT_LABEL[task.repeat_rule]}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
        {tasks.length === 0 && (
          <div className="text-center py-6 text-xs text-zinc-400 border border-dashed border-zinc-200 rounded-lg bg-zinc-50/10">
            当天没有工作事项。
          </div>
        )}
      </div>
    </section>
  );
}

function ReadonlyProblemList({ problems }: { problems: ProblemSolutionOut[] }) {
  return (
    <section className="bg-white rounded-2xl border border-zinc-200 p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] space-y-4">
      <h3 className="text-sm font-bold text-zinc-900">
        问题与解决方案
        <span className="ml-2 text-[11px] text-zinc-400 font-mono font-normal">{problems.length} 条</span>
      </h3>
      <div className="space-y-3">
        {problems.map((problem) => (
          <div key={problem.id} className="rounded-xl p-4 bg-white border border-zinc-100">
            <h4 className="font-semibold text-xs text-zinc-900 leading-snug">{problem.problem_text}</h4>
            {problem.solution_html && (
              <div
                className="tiptap mt-2.5 text-[11px] text-zinc-500 bg-zinc-50/50 p-3 rounded-lg border border-zinc-100 leading-relaxed"
                dangerouslySetInnerHTML={{ __html: problem.solution_html }}
              />
            )}
          </div>
        ))}
        {problems.length === 0 && (
          <div className="text-center py-6 text-xs text-zinc-400 border border-dashed border-zinc-200 rounded-lg bg-zinc-50/10">
            当天没有问题记录。
          </div>
        )}
      </div>
    </section>
  );
}
