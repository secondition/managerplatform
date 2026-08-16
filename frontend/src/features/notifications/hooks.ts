import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as notificationsApi from '@/api/notifications';

const listKey = ['notifications'] as const;
const unreadKey = ['notifications-unread-count'] as const;

export function useNotifications(enabled: boolean) {
  return useInfiniteQuery({
    queryKey: listKey,
    queryFn: ({ pageParam }) => notificationsApi.listNotifications(pageParam),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled,
  });
}

export function useNotificationUnreadCount() {
  return useQuery({
    queryKey: unreadKey,
    queryFn: notificationsApi.getUnreadCount,
    refetchInterval: 30_000,
  });
}

function useInvalidateNotifications() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: listKey });
    queryClient.invalidateQueries({ queryKey: unreadKey });
  };
}

export function useMarkNotificationRead() {
  const invalidate = useInvalidateNotifications();
  return useMutation({ mutationFn: notificationsApi.markNotificationRead, onSuccess: invalidate });
}

export function useMarkAllNotificationsRead() {
  const invalidate = useInvalidateNotifications();
  return useMutation({ mutationFn: notificationsApi.markAllNotificationsRead, onSuccess: invalidate });
}
