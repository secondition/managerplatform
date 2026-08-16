import { AlertTriangle, Bell, CheckCircle2, Send } from 'lucide-react';
import Spinner from '@/components/ui/Spinner';
import {
  useNotificationDeliverySummary,
  useNotificationSettings,
  useTestFeishuNotification,
  useUpdateNotificationSetting,
} from './hooks';

export default function NotificationSettings() {
  const rules = useNotificationSettings();
  const summary = useNotificationDeliverySummary();
  const update = useUpdateNotificationSetting();
  const testFeishu = useTestFeishuNotification();
  const feishuAvailable = rules.data?.[0]?.feishu_available ?? false;

  if (rules.isLoading) return <Spinner label="正在加载通知设置..." />;
  if (rules.isError) {
    return <div className="workspace-card px-5 py-4 text-xs text-red-600">通知设置加载失败，请稍后重试。</div>;
  }

  return (
    <div className="space-y-4">
      <section className="workspace-card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">通知渠道</h2>
            <p className="mt-1 text-[11px] text-slate-500">开关仅影响后续通知，重新开启不会补发历史消息。</p>
          </div>
          <button
            type="button"
            disabled={!feishuAvailable || testFeishu.isPending}
            onClick={() => testFeishu.mutate(undefined)}
            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 text-[11px] font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300"
          >
            <Send size={13} /> {testFeishu.isPending ? '发送中...' : '发送飞书测试'}
          </button>
        </div>

        {!feishuAvailable && (
          <div className="flex items-center gap-2 border-b border-amber-100 bg-amber-50 px-5 py-2.5 text-[11px] text-amber-700">
            <AlertTriangle size={13} /> 部署级飞书通知总开关当前关闭，渠道配置会保存，但不会实际投递。
          </div>
        )}
        {testFeishu.isSuccess && (
          <div className="flex items-center gap-2 border-b border-emerald-100 bg-emerald-50 px-5 py-2.5 text-[11px] text-emerald-700">
            <CheckCircle2 size={13} /> {testFeishu.data.message}
          </div>
        )}
        {testFeishu.isError && (
          <div className="border-b border-red-100 bg-red-50 px-5 py-2.5 text-[11px] text-red-600">
            <strong className="block font-semibold">飞书测试发送失败</strong>
            <p className="mt-1 whitespace-pre-wrap break-all leading-5">{testFeishu.error.message}</p>
          </div>
        )}

        <div className="grid grid-cols-[minmax(0,1fr)_88px_88px] border-b border-slate-100 bg-slate-50 px-5 py-2 text-[10px] font-semibold uppercase text-slate-400">
          <span>通知场景</span><span className="text-center">站内</span><span className="text-center">飞书</span>
        </div>
        {rules.data?.map((rule) => (
          <div key={rule.notification_type} className="grid min-h-16 grid-cols-[minmax(0,1fr)_88px_88px] items-center border-b border-slate-100 px-5 py-3 last:border-0">
            <div className="min-w-0 pr-4">
              <strong className="block truncate text-[12px] font-semibold text-slate-800">{rule.label}</strong>
              <span className="mt-0.5 block text-[10px] leading-4 text-slate-400">{rule.description}</span>
            </div>
            <ChannelSwitch
              label={`${rule.label}站内通知`}
              checked={rule.in_app_enabled}
              disabled={update.isPending}
              onChange={(checked) => update.mutate({ type: rule.notification_type, input: { in_app_enabled: checked } })}
            />
            <ChannelSwitch
              label={`${rule.label}飞书通知`}
              checked={rule.feishu_enabled}
              disabled={update.isPending}
              onChange={(checked) => update.mutate({ type: rule.notification_type, input: { feishu_enabled: checked } })}
            />
          </div>
        ))}
      </section>

      <section className="workspace-card px-5 py-4">
        <div className="flex items-center gap-2"><Bell size={14} className="text-[var(--theme-accent)]" /><h2 className="text-sm font-semibold text-slate-900">飞书投递概况</h2></div>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
          {[
            ['待发送', summary.data?.pending ?? 0],
            ['重试中', summary.data?.retry ?? 0],
            ['已发送', summary.data?.sent ?? 0],
            ['失败', summary.data?.failed ?? 0],
            ['已取消', summary.data?.cancelled ?? 0],
          ].map(([label, value]) => (
            <div key={label} className="border-l-2 border-slate-200 pl-3">
              <strong className="block text-lg font-semibold text-slate-900">{value}</strong>
              <span className="text-[10px] text-slate-400">{label}</span>
            </div>
          ))}
        </div>
        {summary.data?.latest_errors.length ? (
          <div className="mt-4 border-t border-slate-100 pt-3 text-[10px] leading-5 text-red-500">
            {summary.data.latest_errors.map((error, index) => <p key={`${error}-${index}`}>{error}</p>)}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function ChannelSwitch({ label, checked, disabled, onChange }: {
  label: string;
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex justify-center">
      <button
        type="button"
        role="switch"
        aria-label={label}
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 rounded-full transition-colors disabled:opacity-50 ${checked ? 'bg-[var(--theme-accent)]' : 'bg-slate-200'}`}
      >
        <span className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${checked ? 'translate-x-4' : 'translate-x-0'}`} />
      </button>
    </div>
  );
}
