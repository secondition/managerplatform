import { AlertCircle, CheckCircle2, Clock3, RefreshCw } from 'lucide-react';
import Spinner from '@/components/ui/Spinner';
import { dayjs } from '@/lib/date';
import { useContactSyncLogs } from './hooks';

const STATUS_LABEL: Record<string, string> = {
  success: '成功',
  completed: '成功',
  running: '同步中',
  failed: '失败',
};

export default function ContactSyncHistory() {
  const logs = useContactSyncLogs();

  if (logs.isLoading) return <Spinner label="正在加载同步记录..." />;
  if (logs.isError) {
    return (
      <div className="workspace-card flex items-center gap-2 px-4 py-3 text-xs text-red-600">
        <AlertCircle size={14} />
        加载同步记录失败，请稍后重试。
      </div>
    );
  }

  return (
    <section className="workspace-card overflow-hidden">
      <div className="grid grid-cols-[170px_90px_repeat(4,80px)_1fr] border-b border-slate-100 bg-slate-50 px-4 py-3 text-[11px] font-medium text-slate-500">
        <span>开始时间</span>
        <span>状态</span>
        <span>新增</span>
        <span>更新</span>
        <span>禁用</span>
        <span>跳过</span>
        <span>结果</span>
      </div>
      {logs.data?.map((log) => {
        const success = log.status === 'success' || log.status === 'completed';
        const running = log.status === 'running';
        return (
          <div key={log.id} className="grid min-h-12 grid-cols-[170px_90px_repeat(4,80px)_1fr] items-center border-b border-slate-100 px-4 py-3 text-xs text-slate-600 last:border-b-0">
            <span>{dayjs(log.started_at).format('YYYY-MM-DD HH:mm:ss')}</span>
            <span className={`flex items-center gap-1 font-medium ${success ? 'text-emerald-600' : running ? 'text-blue-600' : 'text-red-600'}`}>
              {success ? <CheckCircle2 size={13} /> : running ? <RefreshCw size={13} className="animate-spin" /> : <AlertCircle size={13} />}
              {STATUS_LABEL[log.status] ?? log.status}
            </span>
            <span>{log.created_count}</span>
            <span>{log.updated_count}</span>
            <span>{log.disabled_count}</span>
            <span>{log.skipped_count}</span>
            <span className={log.error_message ? 'text-red-500' : 'text-slate-400'}>
              {log.error_message || (log.finished_at ? `完成于 ${dayjs(log.finished_at).format('HH:mm:ss')}` : <span className="flex items-center gap-1"><Clock3 size={12} />等待完成</span>)}
            </span>
          </div>
        );
      })}
      {logs.data?.length === 0 && (
        <div className="flex min-h-32 items-center justify-center text-xs text-slate-400">还没有通讯录同步记录。</div>
      )}
    </section>
  );
}
