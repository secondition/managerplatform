import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  beginChatAuthorization,
  chatEventSourceUrl,
  parseChatEvent,
} from '@/api/chat';
import { apiErrorCode } from '@/api/client';
import {
  chatAgentStatusKey,
  chatAgentsKey,
  chatMessagesKey,
  useChatAgents,
  useChatAgentStatus,
  useChatMessages,
  useSendChatMessage,
} from './hooks';
import type {
  AssistantFileMessage,
  ChatDisplayMessage,
  ChatEventType,
  ChatMessage,
  ChatMessageListViewState,
  UserTextMessage,
} from './types';

export interface ChatPageNotice {
  tone: 'info' | 'error' | 'success';
  text: string;
}

interface LocalUserMessage extends UserTextMessage {
  client_request_id: string;
  delivery_state: 'sending' | 'sent' | 'failed';
  delivery_error?: string | null;
  server_message_id?: string | null;
}

export function useLiveChat(requestedAgentKey: string | null, enabled: boolean) {
  const queryClient = useQueryClient();
  const agentsQuery = useChatAgents(enabled);
  const agents = agentsQuery.data ?? [];
  const selectedAgent = (
    agents.find((agent) => agent.agent_key === requestedAgentKey)
    ?? agents[0]
    ?? null
  );
  const selectedAgentKey = selectedAgent?.agent_key ?? null;
  const statusQuery = useChatAgentStatus(selectedAgentKey, enabled);
  const selectedStatus = statusQuery.data ?? null;
  const messagesEnabled = enabled && selectedStatus?.can_read === true;
  const messagesQuery = useChatMessages(selectedAgentKey, messagesEnabled);
  const sendMutation = useSendChatMessage(selectedAgentKey);
  const [localMessages, setLocalMessages] = useState<Record<string, LocalUserMessage[]>>({});
  const [notice, setNotice] = useState<ChatPageNotice | null>(null);
  const [authorizing, setAuthorizing] = useState(false);
  const [sseConnected, setSseConnected] = useState(false);
  const refreshTimers = useRef<number[]>([]);

  const serverMessages = useMemo(
    () => flattenMessagePages(messagesQuery.data?.pages ?? []),
    [messagesQuery.data?.pages],
  );
  const selectedLocalMessages = selectedAgentKey
    ? localMessages[selectedAgentKey] ?? []
    : [];

  useEffect(() => {
    if (!agentsQuery.isSuccess) return;
    const grantedAgentKeys = new Set(agents.map((agent) => agent.agent_key));
    setLocalMessages((current) => {
      const next = Object.fromEntries(
        Object.entries(current).filter(([agentKey]) => grantedAgentKeys.has(agentKey)),
      );
      return Object.keys(next).length === Object.keys(current).length ? current : next;
    });
  }, [agents, agentsQuery.isSuccess]);

  useEffect(() => {
    if (!selectedAgentKey || serverMessages.length === 0) return;
    setLocalMessages((current) => {
      const currentMessages = current[selectedAgentKey] ?? [];
      const nextMessages = removeReconciledLocalMessages(currentMessages, serverMessages);
      if (nextMessages.length === currentMessages.length) return current;
      return { ...current, [selectedAgentKey]: nextMessages };
    });
  }, [selectedAgentKey, serverMessages]);

  useEffect(() => {
    if (!selectedAgentKey || !selectedStatus || selectedStatus.can_read) return;
    queryClient.removeQueries({ queryKey: chatMessagesKey(selectedAgentKey) });
    setLocalMessages((current) => {
      if (!current[selectedAgentKey]) return current;
      const next = { ...current };
      delete next[selectedAgentKey];
      return next;
    });
  }, [queryClient, selectedAgentKey, selectedStatus]);

  useEffect(() => () => {
    refreshTimers.current.forEach((timer) => window.clearTimeout(timer));
  }, []);

  useEffect(() => {
    if (!enabled || !selectedAgentKey || !selectedStatus?.can_read) {
      setSseConnected(false);
      return;
    }
    const eventSource = new EventSource(chatEventSourceUrl(selectedAgentKey), {
      withCredentials: true,
    });
    const eventTypes: ChatEventType[] = [
      'ready',
      'message.created',
      'message.updated',
      'message.deleted',
      'agent.access_revoked',
      'authorization.required',
      'sync.delayed',
      'heartbeat',
    ];

    const handleEvent = (rawEvent: Event) => {
      if (!(rawEvent instanceof MessageEvent)) return;
      const event = parseChatEvent(String(rawEvent.data));
      if (!event || event.agent_key !== selectedAgentKey) return;
      if (event.event.startsWith('message.') || event.event === 'ready') {
        void queryClient.invalidateQueries({ queryKey: chatMessagesKey(selectedAgentKey) });
      }
      if (
        event.event === 'sync.delayed'
        || event.event === 'authorization.required'
        || event.event === 'agent.access_revoked'
      ) {
        if (
          event.event === 'authorization.required'
          || event.event === 'agent.access_revoked'
        ) {
          queryClient.removeQueries({ queryKey: chatMessagesKey(selectedAgentKey) });
        }
        void queryClient.invalidateQueries({ queryKey: chatAgentsKey });
        void queryClient.invalidateQueries({ queryKey: chatAgentStatusKey(selectedAgentKey) });
      }
    };

    eventSource.onopen = () => setSseConnected(true);
    eventSource.onerror = () => {
      setSseConnected(false);
      void statusQuery.refetch();
    };
    eventTypes.forEach((eventType) => eventSource.addEventListener(eventType, handleEvent));
    return () => {
      eventTypes.forEach((eventType) => eventSource.removeEventListener(eventType, handleEvent));
      eventSource.close();
      setSseConnected(false);
    };
  }, [enabled, queryClient, selectedAgentKey, selectedStatus?.can_read, statusQuery.refetch]);

  const messages = useMemo<ChatDisplayMessage[]>(
    () => [...serverMessages, ...selectedLocalMessages],
    [selectedLocalMessages, serverMessages],
  );

  const messageList = useMemo<ChatMessageListViewState>(() => {
    if (!messagesEnabled) {
      return { status: 'ready', has_more: false, error_message: null };
    }
    if (messagesQuery.isPending) {
      return { status: 'loading', has_more: false, error_message: null };
    }
    if (messagesQuery.isFetchingNextPage) {
      return {
        status: 'loading_more',
        has_more: messagesQuery.hasNextPage,
        error_message: null,
      };
    }
    if (messagesQuery.isError) {
      return {
        status: 'error',
        has_more: messagesQuery.hasNextPage,
        error_message: chatErrorMessage(messagesQuery.error, '聊天记录加载失败，请稍后重试。'),
      };
    }
    return {
      status: 'ready',
      has_more: messagesQuery.hasNextPage,
      error_message: null,
    };
  }, [messagesEnabled, messagesQuery.error, messagesQuery.hasNextPage, messagesQuery.isError, messagesQuery.isFetchingNextPage, messagesQuery.isPending]);

  const updateLocalMessage = useCallback((
    agentKey: string,
    clientRequestId: string,
    changes: Partial<LocalUserMessage>,
  ) => {
    setLocalMessages((current) => ({
      ...current,
      [agentKey]: (current[agentKey] ?? []).map((message) => (
        message.client_request_id === clientRequestId
          ? { ...message, ...changes }
          : message
      )),
    }));
  }, []);

  const send = useCallback((
    agentKey: string,
    text: string,
    clientRequestId: string,
  ) => {
    updateLocalMessage(agentKey, clientRequestId, {
      delivery_state: 'sending',
      delivery_error: null,
    });
    void sendMutation.mutateAsync({ text, client_request_id: clientRequestId })
      .then((result) => {
        if (result.status === 'failed') {
          updateLocalMessage(agentKey, clientRequestId, {
            delivery_state: 'failed',
            delivery_error: result.error_message ?? sendErrorMessage(result.error_code),
          });
          return;
        }
        updateLocalMessage(agentKey, clientRequestId, {
          delivery_state: 'sent',
          delivery_error: null,
          server_message_id: result.message_id,
        });
        void queryClient.invalidateQueries({ queryKey: chatMessagesKey(agentKey) });
        void queryClient.invalidateQueries({ queryKey: chatAgentStatusKey(agentKey) });
        [2_000, 6_000, 15_000].forEach((delay) => {
          refreshTimers.current.push(window.setTimeout(() => {
            void queryClient.invalidateQueries({ queryKey: chatMessagesKey(agentKey) });
          }, delay));
        });
      })
      .catch((error: unknown) => {
        updateLocalMessage(agentKey, clientRequestId, {
          delivery_state: 'failed',
          delivery_error: chatErrorMessage(error, '消息发送失败，请稍后重试。'),
        });
      });
  }, [queryClient, sendMutation, updateLocalMessage]);

  const submitMessage = useCallback((text: string) => {
    if (!selectedAgentKey || sendMutation.isPending) return false;
    const clientRequestId = createClientRequestId();
    const optimistic: LocalUserMessage = {
      id: `local-${clientRequestId}`,
      role: 'user',
      kind: 'user_text',
      body_text: text,
      client_request_id: clientRequestId,
      created_at: new Date().toISOString(),
      delivery_state: 'sending',
      delivery_error: null,
    };
    setLocalMessages((current) => ({
      ...current,
      [selectedAgentKey]: [...(current[selectedAgentKey] ?? []), optimistic],
    }));
    send(selectedAgentKey, text, clientRequestId);
    return true;
  }, [selectedAgentKey, send, sendMutation.isPending]);

  const retryMessage = useCallback((message: ChatDisplayMessage) => {
    if (
      !selectedAgentKey
      || message.kind !== 'user_text'
      || !message.client_request_id
      || message.delivery_state !== 'failed'
      || sendMutation.isPending
    ) {
      return;
    }
    send(selectedAgentKey, message.body_text, message.client_request_id);
  }, [selectedAgentKey, send, sendMutation.isPending]);

  const authorize = useCallback(() => {
    if (!selectedAgentKey || authorizing) return;
    setAuthorizing(true);
    setNotice({ tone: 'info', text: '正在打开飞书授权页面…' });
    void beginChatAuthorization(selectedAgentKey)
      .then((result) => {
        const authorizeUrl = safeFeishuAuthorizeUrl(result.authorize_url);
        if (!authorizeUrl) throw new Error('Unsafe authorization URL');
        window.location.assign(authorizeUrl);
      })
      .catch((error: unknown) => {
        setNotice({
          tone: 'error',
          text: chatErrorMessage(error, '暂时无法发起飞书授权，请稍后重试。'),
        });
        setAuthorizing(false);
      });
  }, [authorizing, selectedAgentKey]);

  const attachmentAction = useCallback((message: AssistantFileMessage) => {
    setNotice({
      tone: 'info',
      text: `“${message.file_name}”当前无法通过网页下载，请前往目标飞书群查看。`,
    });
  }, []);

  const retryMessages = useCallback(() => {
    void messagesQuery.refetch();
  }, [messagesQuery]);

  const loadMore = useCallback(() => {
    if (messagesQuery.hasNextPage && !messagesQuery.isFetchingNextPage) {
      void messagesQuery.fetchNextPage();
    }
  }, [messagesQuery]);

  const retryBootstrap = useCallback(() => {
    void agentsQuery.refetch();
    if (selectedAgentKey) void statusQuery.refetch();
  }, [agentsQuery, selectedAgentKey, statusQuery]);

  const pageLoading = enabled && (
    agentsQuery.isPending
    || (Boolean(selectedAgent) && statusQuery.isPending)
  );
  const pageError = enabled && agentsQuery.isError
    ? chatErrorMessage(agentsQuery.error, '智能体列表加载失败，请稍后重试。')
    : enabled && statusQuery.isError
      ? chatErrorMessage(statusQuery.error, '智能体状态加载失败，请稍后重试。')
      : null;

  return {
    agents,
    selectedAgent,
    selectedStatus,
    selectedAgentKey,
    messages,
    messageList,
    notice,
    pageLoading,
    pageError,
    composerSubmitting: sendMutation.isPending,
    authorizing,
    helperText: sseConnected
      ? 'Enter 发送，Shift + Enter 换行 · 实时更新已连接'
      : 'Enter 发送，Shift + Enter 换行 · 消息将安全同步到飞书',
    setNotice,
    submitMessage,
    retryMessage,
    authorize,
    attachmentAction,
    retryMessages,
    loadMore,
    retryBootstrap,
  };
}

function removeReconciledLocalMessages(
  localMessages: LocalUserMessage[],
  serverMessages: ChatMessage[],
) {
  const requestIds = new Set(
    serverMessages
      .filter((message): message is UserTextMessage => message.kind === 'user_text')
      .map((message) => message.client_request_id)
      .filter((value): value is string => Boolean(value)),
  );
  const messageIds = new Set(serverMessages.map((message) => message.id));
  const serverUserMessages = serverMessages.filter(
    (message): message is UserTextMessage => message.kind === 'user_text',
  );
  const matchedServerMessageIds = new Set<string>();

  return localMessages.filter((localMessage) => {
    if (requestIds.has(localMessage.client_request_id)) return false;
    if (
      localMessage.server_message_id
      && messageIds.has(localMessage.server_message_id)
    ) {
      return false;
    }
    if (localMessage.delivery_state !== 'sent') return true;

    const localCreatedAt = Date.parse(localMessage.created_at);
    if (Number.isNaN(localCreatedAt)) return true;
    const matchingMessage = serverUserMessages.find((serverMessage) => {
      if (
        matchedServerMessageIds.has(serverMessage.id)
        || serverMessage.body_text !== localMessage.body_text
      ) {
        return false;
      }
      const serverCreatedAt = Date.parse(serverMessage.created_at);
      if (Number.isNaN(serverCreatedAt)) return false;
      return serverCreatedAt >= localCreatedAt - 5_000
        && serverCreatedAt <= localCreatedAt + 120_000;
    });
    if (!matchingMessage) return true;
    matchedServerMessageIds.add(matchingMessage.id);
    return false;
  });
}

function flattenMessagePages(pages: Array<{ items: ChatMessage[] }>) {
  const seen = new Set<string>();
  const messages: ChatMessage[] = [];
  [...pages].reverse().forEach((page) => {
    page.items.forEach((message) => {
      if (seen.has(message.id)) return;
      seen.add(message.id);
      messages.push(message);
    });
  });
  return messages;
}

function createClientRequestId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `web-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

function safeFeishuAuthorizeUrl(value: string) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:') return null;
    if (url.hostname !== 'accounts.feishu.cn' && !url.hostname.endsWith('.feishu.cn')) {
      return null;
    }
    return url.toString();
  } catch {
    return null;
  }
}

function chatErrorMessage(error: unknown, fallback: string) {
  return errorMessageForCode(apiErrorCode(error)) ?? fallback;
}

function sendErrorMessage(code: string | null) {
  return errorMessageForCode(code) ?? '消息发送失败，请稍后重试。';
}

function errorMessageForCode(code: string | null) {
  if (!code) return null;
  const messages: Record<string, string> = {
    authorization_required: '飞书授权已失效，请重新启用查宝。',
    not_chat_member: '你当前不在查宝安全群中。',
    membership_not_synchronized: '正在核验飞书群成员资格，请稍后重试。',
    membership_snapshot_stale: '群成员信息需要重新同步，请稍后重试。',
    initial_sync_pending: '正在建立消息投影，请稍后重试。',
    sync_delayed: '飞书消息同步存在延迟，请稍后重试。',
    sync_blocked: '消息同步当前不可用，请联系管理员。',
    chat_disabled: '聊天功能当前处于维护状态。',
    message_empty: '请输入消息内容。',
    message_too_long: '消息内容超过长度限制。',
    message_contains_control_characters: '消息包含不支持的控制字符。',
    idempotency_key_conflict: '该重试请求与原消息不一致，请重新发送。',
    send_rate_limited: '发送过于频繁，请稍后重试。',
    send_service_unavailable: '飞书服务暂时不可用，请稍后重试。',
    invalid_cursor: '历史消息游标已失效，请重新加载。',
  };
  return messages[code] ?? null;
}
