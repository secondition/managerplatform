import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import * as chatApi from '@/api/chat';
import type { SendChatMessageRequest } from './types';

export const chatAgentsKey = ['chat-agents'] as const;

export function chatAgentStatusKey(agentKey: string) {
  return ['chat-agent-status', agentKey] as const;
}

export function chatMessagesKey(agentKey: string) {
  return ['chat-messages', agentKey] as const;
}

export function useChatAgents(enabled: boolean) {
  return useQuery({
    queryKey: chatAgentsKey,
    queryFn: ({ signal }) => chatApi.listChatAgents(signal),
    enabled,
    staleTime: 10_000,
    refetchInterval: enabled ? 15_000 : false,
  });
}

export function useChatAgentStatus(agentKey: string | null, enabled: boolean) {
  return useQuery({
    queryKey: chatAgentStatusKey(agentKey ?? 'none'),
    queryFn: ({ signal }) => chatApi.getChatAgentStatus(agentKey!, signal),
    enabled: enabled && Boolean(agentKey),
    staleTime: 5_000,
    refetchInterval: enabled && agentKey ? 15_000 : false,
  });
}

export function useChatMessages(agentKey: string | null, enabled: boolean) {
  return useInfiniteQuery({
    queryKey: chatMessagesKey(agentKey ?? 'none'),
    queryFn: ({ pageParam, signal }) => chatApi.listChatMessages(agentKey!, {
      cursor: pageParam,
      limit: 50,
      signal,
    }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: enabled && Boolean(agentKey),
    staleTime: 3_000,
  });
}

export function useSendChatMessage(agentKey: string | null) {
  return useMutation({
    mutationFn: (payload: SendChatMessageRequest) => {
      if (!agentKey) throw new Error('No chat agent selected');
      return chatApi.sendChatMessage(agentKey, payload);
    },
  });
}

export function useInvalidateChat() {
  const queryClient = useQueryClient();
  return {
    agents: () => queryClient.invalidateQueries({ queryKey: chatAgentsKey }),
    status: (agentKey: string) => queryClient.invalidateQueries({
      queryKey: chatAgentStatusKey(agentKey),
    }),
    messages: (agentKey: string) => queryClient.invalidateQueries({
      queryKey: chatMessagesKey(agentKey),
    }),
    all: (agentKey: string) => Promise.all([
      queryClient.invalidateQueries({ queryKey: chatAgentsKey }),
      queryClient.invalidateQueries({ queryKey: chatAgentStatusKey(agentKey) }),
      queryClient.invalidateQueries({ queryKey: chatMessagesKey(agentKey) }),
    ]),
  };
}
