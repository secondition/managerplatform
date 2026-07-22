import { useMemo, useState, type ReactNode } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  CalendarDays,
  Check,
  CheckCircle2,
  Clock3,
  Edit3,
  Loader2,
  MessageSquareText,
  Star,
  UserPlus,
  X,
} from 'lucide-react';
import Avatar from '@/components/user/Avatar';
import Spinner from '@/components/ui/Spinner';
import { useAuthStore } from '@/stores/authStore';
import { dayjs, toApiMonth } from '@/lib/date';
import type { PersonAiScoreOut, PersonCalendarDayOut, PersonProfileOut } from '@/types/api';
import {
  usePersonProfile,
  useSubscribePerson,
  useUnsubscribePerson,
  useUpdateMySignature,
} from './hooks';

const ROLE_LABEL: Record<string, string> = {
  owner: 'Owner',
  member: '成员',
};

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

export default function PeoplePage() {
  const params = useParams();
  const profileUserId = params.userId ? Number(params.userId) : 'me';
  const [monthValue, setMonthValue] = useState(() => toApiMonth(dayjs()));
  const profile = usePersonProfile(profileUserId, monthValue);

  if (Number.isNaN(profileUserId)) {
    return <ProfileShell><EmptyMessage title="用户不存在" desc="当前个人主页地址不正确。" /></ProfileShell>;
  }

  if (profile.isLoading) {
    return (
      <ProfileShell>
        <div className="py-20">
          <Spinner label="正在加载个人主页..." />
        </div>
      </ProfileShell>
    );
  }

  if (profile.isError || !profile.data) {
    return <ProfileShell><EmptyMessage title="加载失败" desc="无法打开这个人的主页，可能用户已停用或不存在。" /></ProfileShell>;
  }

  return (
    <ProfileShell>
      <div className="space-y-5">
        <ProfileHeader profile={profile.data} />

        <section className="grid grid-cols-1 lg:grid-cols-[420px_minmax(0,1fr)] gap-5">
          <DailyCalendarPanel
            profile={profile.data}
            isFetching={profile.isFetching}
            monthValue={monthValue}
            onMonthChange={setMonthValue}
          />
          <MonthlyStats profile={profile.data} isFetching={profile.isFetching} />
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <ScoreCard
            icon={<Star size={16} />}
            title="今日日报评分"
            score={profile.data.daily_score}
            period="today"
            empty="今日暂无 AI 日报评分。"
            profile={profile.data}
            target="daily"
          />
          <ScoreCard
            icon={<MessageSquareText size={16} />}
            title="本月 OKR 点评"
            score={profile.data.okr_review}
            period="month"
            empty="本月暂无 OKR 点评。"
            profile={profile.data}
            target="okr"
          />
        </section>
      </div>
    </ProfileShell>
  );
}

function ProfileShell({ children }: { children: ReactNode }) {
  return <div className="max-w-[1120px] w-full mx-auto px-4 md:px-8 py-6">{children}</div>;
}

function ProfileHeader({ profile }: { profile: PersonProfileOut }) {
  return (
    <section className="bg-white rounded-2xl p-5 md:p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <ProfileAvatar profile={profile} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-bold text-zinc-950 truncate">{profile.user.name}</h2>
              {profile.is_self && (
                <span className="rounded-full bg-[var(--theme-accent-soft)] text-[var(--theme-accent)] px-2 py-0.5 text-[11px] font-medium">
                  我的主页
                </span>
              )}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
              <span>{ROLE_LABEL[profile.user.role] ?? profile.user.role}</span>
              <MetaDivider />
              <span>{profile.user.department_name ?? '未归属'}</span>
              <MetaDivider />
              <span>最近登录 {formatDateTime(profile.user.last_login_at)}</span>
              {profile.user.email && (
                <>
                  <MetaDivider />
                  <span>{profile.user.email}</span>
                </>
              )}
            </div>
            <div className="mt-3 flex items-center gap-4 text-xs">
              <SocialCount label="关注" value={profile.social.following_count} />
              <SocialCount label="粉丝" value={profile.social.followers_count} />
            </div>
          </div>
        </div>
        {!profile.is_self && <SubscribeButton profile={profile} />}
      </div>

      <SignatureBlock profile={profile} />
    </section>
  );
}

function ProfileAvatar({ profile }: { profile: PersonProfileOut }) {
  // Avatars are fixed to the name initials; there is no upload entry anymore.
  return <Avatar name={profile.user.name} size={58} />;
}

function MetaDivider() {
  return <span className="text-zinc-300">|</span>;
}

function SocialCount({ label, value }: { label: string; value: number }) {
  return (
    <span className="inline-flex items-baseline gap-1 text-zinc-500">
      <b className="text-sm text-zinc-900">{value}</b>
      <span>{label}</span>
    </span>
  );
}

function SubscribeButton({ profile }: { profile: PersonProfileOut }) {
  const subscribe = useSubscribePerson(profile.user.id);
  const unsubscribe = useUnsubscribePerson(profile.user.id);
  const pending = subscribe.isPending || unsubscribe.isPending;
  const subscribed = profile.subscription.subscribed;

  return (
    <button
      onClick={() => (subscribed ? unsubscribe.mutate() : subscribe.mutate())}
      disabled={pending}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-60 shrink-0 ${
        subscribed
          ? 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200'
          : 'bg-[var(--theme-accent)] text-white hover:bg-[var(--theme-accent-hover)]'
      }`}
    >
      {pending ? <Loader2 size={14} className="animate-spin" /> : subscribed ? <CheckCircle2 size={14} /> : <UserPlus size={14} />}
      {subscribed ? '已订阅' : '订阅'}
    </button>
  );
}

function SignatureBlock({ profile }: { profile: PersonProfileOut }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(profile.user.profile_signature ?? '');
  const updateSignature = useUpdateMySignature();
  const signature = profile.user.profile_signature?.trim();

  const startEdit = () => {
    setValue(profile.user.profile_signature ?? '');
    setEditing(true);
  };

  const cancelEdit = () => {
    setValue(profile.user.profile_signature ?? '');
    setEditing(false);
  };

  const save = () => {
    updateSignature.mutate(value, {
      onSuccess: () => setEditing(false),
    });
  };

  return (
    <div className="mt-5 rounded-xl bg-zinc-50 px-4 py-3">
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="text-[11px] text-zinc-400">个性签名</div>
        {profile.is_self && !editing && (
          <button
            onClick={startEdit}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] text-[var(--theme-accent)] hover:bg-[var(--theme-accent-soft)] cursor-pointer"
          >
            <Edit3 size={12} />
            编辑
          </button>
        )}
      </div>
      {editing ? (
        <div className="space-y-2">
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value.slice(0, 200))}
            rows={3}
            className="w-full resize-none rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-700 outline-none focus:border-[var(--theme-accent)] focus:shadow-[0_0_0_3px_var(--theme-accent-ring)]"
            placeholder="写一句想让同事看到的话"
          />
          <div className="flex items-center justify-between gap-3">
            <span className="text-[11px] text-zinc-400">{value.length}/200</span>
            <div className="flex items-center gap-2">
              <button
                onClick={cancelEdit}
                disabled={updateSignature.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] text-zinc-500 hover:bg-zinc-100 disabled:opacity-50 cursor-pointer"
              >
                <X size={12} />
                取消
              </button>
              <button
                onClick={save}
                disabled={updateSignature.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--theme-accent)] px-2.5 py-1.5 text-[11px] font-medium text-white hover:bg-[var(--theme-accent-hover)] disabled:opacity-50 cursor-pointer"
              >
                {updateSignature.isPending ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                保存
              </button>
            </div>
          </div>
        </div>
      ) : (
        <p className={`text-xs ${signature ? 'text-zinc-600' : 'text-zinc-400'}`}>
          {signature || '这个人还没有填写签名。'}
        </p>
      )}
    </div>
  );
}

function DailyCalendarPanel({
  profile,
  isFetching,
  monthValue,
  onMonthChange,
}: {
  profile: PersonProfileOut;
  isFetching: boolean;
  monthValue: string;
  onMonthChange: (value: string) => void;
}) {
  return (
    <section className="bg-white rounded-2xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h3 className="text-sm font-bold text-zinc-900 flex items-center gap-2">
          <CalendarDays size={16} className="text-[var(--theme-icon-color)]" />
          日报日历
        </h3>
        <input
          type="month"
          value={monthValue}
          onChange={(e) => onMonthChange(e.target.value)}
          className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs text-zinc-700 outline-none focus:border-[var(--theme-accent)]"
        />
      </div>
      {isFetching && (
        <div className="mb-2 inline-flex items-center gap-1.5 text-[11px] text-[var(--theme-accent)]">
          <Loader2 size={11} className="animate-spin" />
          更新日历中
        </div>
      )}
      <DailyCalendar days={profile.daily_calendar.days} />
      <div className="mt-4 flex flex-wrap items-center gap-3 text-[11px] text-zinc-500">
        <LegendDot className="bg-blue-500" label="有日报" />
        <LegendDot className="bg-red-500" label="缺日报" />
        <LegendDot className="border border-zinc-200" label="无需" />
      </div>
    </section>
  );
}

function MonthlyStats({ profile, isFetching }: { profile: PersonProfileOut; isFetching: boolean }) {
  const calendar = profile.daily_calendar;
  const completionText =
    calendar.task_completion_rate === null
      ? '暂无'
      : `${Math.round(calendar.task_completion_rate * 100)}%`;

  return (
    <section className="bg-white rounded-2xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-sm font-bold text-zinc-900">本月日报概览</h3>
          <p className="text-xs text-zinc-400 mt-1">
            {isFetching ? '正在更新月份数据...' : '工作清单完成率统计到已结束工作日，今日 20:00 后纳入。'}
          </p>
        </div>
        <Clock3 size={16} className="text-zinc-300 shrink-0" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 gap-3">
        <MetricTile label="日报存在数量" value={`${calendar.done_days}`} suffix="天" tone="blue" />
        <MetricTile label="日报缺少数量" value={`${calendar.missing_days}`} suffix="天" tone="red" />
        <MetricTile
          label="工作清单平均完成率"
          value={completionText}
          hint={calendar.total_tasks ? `${calendar.completed_tasks}/${calendar.total_tasks} 项` : '暂无任务'}
          tone="green"
        />
      </div>
    </section>
  );
}

function MetricTile({
  label,
  value,
  suffix,
  hint,
  tone,
}: {
  label: string;
  value: string;
  suffix?: string;
  hint?: string;
  tone: 'blue' | 'red' | 'green';
}) {
  const toneClass = {
    blue: 'text-blue-600',
    red: 'text-red-600',
    green: 'text-emerald-600',
  }[tone];
  return (
    <div className="rounded-xl bg-zinc-50 px-4 py-4">
      <div className="text-[11px] text-zinc-400">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${toneClass}`}>
        {value}
        {suffix && <span className="ml-1 text-xs font-medium text-zinc-400">{suffix}</span>}
      </div>
      {hint && <div className="mt-1 text-[11px] text-zinc-400">{hint}</div>}
    </div>
  );
}

function ScoreCard({
  icon,
  title,
  score,
  period,
  empty,
  profile,
  target,
}: {
  icon: ReactNode;
  title: string;
  score: PersonAiScoreOut;
  period: 'today' | 'month';
  empty: string;
  profile: PersonProfileOut;
  target: 'daily' | 'okr';
}) {
  const navigate = useNavigate();
  const hasPermission = useAuthStore((s) => s.hasPermission);

  // Only surface the score when it belongs to the current period: daily scores
  // must be from today, OKR reviews from the current month.
  const inPeriod =
    score.status === 'ready' &&
    score.score !== null &&
    !!score.updated_at &&
    dayjs(score.updated_at).isSame(dayjs(), period === 'today' ? 'day' : 'month');

  // Clicking jumps to the matching feature: own profile → the editable page,
  // others → the read-only subscription view. Gated by the feature permission.
  const permission = target === 'daily' ? 'feature:daily' : 'feature:okr';
  const canNavigate = hasPermission(permission);
  const destination = profile.is_self
    ? target === 'daily' ? '/daily' : '/okr'
    : target === 'daily' ? '/subscription/daily' : '/subscription/okr';
  // For a colleague, hand the subscription page the user id through router
  // state so it can pre-select them — no URL param needed.
  const navState = profile.is_self ? undefined : { subscriptionUserId: profile.user.id };
  const go = () => navigate(destination, navState ? { state: navState } : undefined);

  return (
    <section
      role={canNavigate ? 'button' : undefined}
      tabIndex={canNavigate ? 0 : undefined}
      onClick={canNavigate ? go : undefined}
      onKeyDown={
        canNavigate
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                go();
              }
            }
          : undefined
      }
      className={`bg-white rounded-2xl border border-zinc-200 p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] min-h-[160px] transition-colors ${
        canNavigate ? 'cursor-pointer hover:border-[var(--theme-accent)] hover:bg-[var(--theme-accent-soft)]' : ''
      }`}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-zinc-900 flex items-center gap-2">
          <span className="text-[var(--theme-icon-color)]">{icon}</span>
          {title}
        </h3>
        {inPeriod ? (
          <span className="text-[11px] text-zinc-400">{score.updated_at?.slice(0, 10)}</span>
        ) : (
          <span className="text-[11px] text-zinc-400">{period === 'today' ? '今日未生成' : '本月未生成'}</span>
        )}
      </div>
      {inPeriod ? (
        <div className="mt-5">
          <div className="text-3xl font-bold text-[var(--theme-accent)]">{score.score}</div>
          <p className="text-xs text-zinc-500 mt-3 leading-relaxed">{score.summary}</p>
        </div>
      ) : (
        <div className="mt-6 rounded-xl border border-dashed border-zinc-200 bg-zinc-50/50 px-4 py-5">
          <p className="text-xs text-zinc-400 leading-relaxed">{empty}</p>
        </div>
      )}
    </section>
  );
}

function DailyCalendar({ days }: { days: PersonCalendarDayOut[] }) {
  const cells = useMemo(() => {
    if (days.length === 0) return [];
    const first = dayjs(days[0].date);
    const prefix = first.day();
    return [
      ...Array.from({ length: prefix }, (_, index) => ({ key: `blank-${index}`, day: null })),
      ...days.map((day) => ({ key: day.date, day })),
    ];
  }, [days]);

  return (
    <div className="max-w-[320px]">
      <div className="grid grid-cols-7 gap-1 mb-1.5">
        {WEEKDAYS.map((weekday) => (
          <div key={weekday} className="text-center text-[10px] text-zinc-400 py-0.5">
            {weekday}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((cell) =>
          cell.day ? (
            <CalendarCell key={cell.key} day={cell.day} />
          ) : (
            <div key={cell.key} className="h-8 rounded-md" />
          ),
        )}
      </div>
    </div>
  );
}

function CalendarCell({ day }: { day: PersonCalendarDayOut }) {
  const dayNumber = dayjs(day.date).date();
  const dotClass =
    day.state === 'done'
      ? 'bg-blue-500'
      : day.state === 'missing'
        ? 'bg-red-500'
        : 'bg-transparent';
  return (
    <div
      title={day.date}
      className={`h-8 rounded-md border flex flex-col items-center justify-center gap-0.5 ${
        day.is_future || !day.is_workday
          ? 'border-zinc-100 bg-zinc-50/40 text-zinc-300'
          : 'border-zinc-100 bg-white text-zinc-700'
      }`}
    >
      <span className="text-[11px] leading-none font-medium">{dayNumber}</span>
      <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
    </div>
  );
}

function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${className}`} />
      {label}
    </span>
  );
}

function formatDateTime(value: string | null): string {
  if (!value) return '暂无';
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return '暂无';
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

function EmptyMessage({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="bg-white rounded-2xl p-10 shadow-[0_8px_30px_rgb(0,0,0,0.02)] text-center">
      <h3 className="text-sm font-bold text-zinc-800">{title}</h3>
      <p className="text-xs text-zinc-400 mt-2">{desc}</p>
    </div>
  );
}

