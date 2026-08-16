import { useRef, useState } from 'react';
import { Bell, CheckCheck, LoaderCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AnchoredPopover from '@/components/ui/AnchoredPopover';
import { dayjs } from '@/lib/date';
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useNotificationUnreadCount,
} from './hooks';

export default function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();
  const unread = useNotificationUnreadCount();
  const notifications = useNotifications(open);
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllNotificationsRead();
  const items = notifications.data?.pages.flatMap((page) => page.items) ?? [];
  const count = unread.data?.count ?? 0;

  const openNotification = async (id: number, actionUrl: string | null, isRead: boolean) => {
    if (!isRead) await markRead.mutateAsync(id);
    setOpen(false);
    if (actionUrl) navigate(actionUrl);
  };

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label="通知中心"
        aria-expanded={open}
        className={`relative rounded-md p-1.5 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 ${open ? 'bg-slate-100 text-slate-800' : ''}`}
        title="通知中心"
      >
        <Bell size={15} />
        {count > 0 && (
          <span className="absolute -right-1.5 -top-1.5 flex min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-semibold leading-4 text-white">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>

      <AnchoredPopover
        anchor={open ? triggerRef.current : null}
        width={380}
        align="end"
        borderRadius={8}
        zIndex={1300}
        onClose={() => setOpen(false)}
      >
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <div className="flex h-11 items-center justify-between border-b border-slate-100 px-4">
            <div className="flex items-baseline gap-2">
              <h3 className="text-sm font-semibold text-slate-900">通知</h3>
              {count > 0 && <span className="text-[11px] text-slate-400">{count} 条未读</span>}
            </div>
            <button
              type="button"
              disabled={count === 0 || markAll.isPending}
              onClick={() => markAll.mutate()}
              className="inline-flex items-center gap-1 text-[11px] text-[var(--theme-accent)] disabled:text-slate-300"
            >
              <CheckCheck size={13} /> 全部已读
            </button>
          </div>

          <div className="max-h-[440px] overflow-y-auto">
            {notifications.isLoading ? (
              <div className="flex h-28 items-center justify-center text-slate-400"><LoaderCircle className="animate-spin" size={18} /></div>
            ) : notifications.isError ? (
              <div className="px-5 py-10 text-center text-xs text-red-500">通知加载失败，请稍后重试</div>
            ) : items.length === 0 ? (
              <div className="px-5 py-12 text-center text-xs text-slate-400">暂无通知</div>
            ) : (
              items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => openNotification(item.id, item.action_url, Boolean(item.read_at))}
                  className={`relative block w-full border-b border-slate-100 px-4 py-3 text-left last:border-0 hover:bg-slate-50 ${item.read_at ? 'bg-white' : 'bg-blue-50/40'}`}
                >
                  {!item.read_at && <span className="absolute left-1.5 top-5 h-1.5 w-1.5 rounded-full bg-[var(--theme-accent)]" />}
                  <span className="block pr-16 text-[12px] font-semibold text-slate-800">{item.title}</span>
                  <span className="mt-1 block text-[11px] leading-5 text-slate-500">{item.body}</span>
                  <time className="mt-1.5 block text-[10px] text-slate-400">{dayjs(item.created_at).format('MM-DD HH:mm')}</time>
                </button>
              ))
            )}
          </div>
          {notifications.hasNextPage && (
            <button
              type="button"
              disabled={notifications.isFetchingNextPage}
              onClick={() => notifications.fetchNextPage()}
              className="h-9 w-full border-t border-slate-100 text-[11px] text-slate-500 hover:bg-slate-50"
            >
              {notifications.isFetchingNextPage ? '加载中...' : '查看更多'}
            </button>
          )}
        </div>
      </AnchoredPopover>
    </>
  );
}
