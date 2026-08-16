import { api } from './client';
import type {
  ChatAgentStatus,
  ChatAgentSummary,
  ChatEvent,
  ChatMessagePage,
  SendChatMessageRequest,
  SendChatMessageResponse,
} from '@/features/chat/types';

export interface ChatAuthorizeResponse {
  authorize_url: string;
  return_to: string;
}

export interface ChatOAuthCallbackResponse {
  agent_key: string;
  credential_status: 'active';
  return_to: string;
}

export interface ChatDisconnectResponse {
  ok: boolean;
  credential_status: 'revoked';
}

export function listChatAgents(signal?: AbortSignal) {
  return api<ChatAgentSummary[]>('/chat/agents', { signal });
}

export function getChatAgentStatus(agentKey: string, signal?: AbortSignal) {
  return api<ChatAgentStatus>(
    `/chat/agents/${encodeURIComponent(agentKey)}/status`,
    { signal },
  );
}

export function listChatMessages(
  agentKey: string,
  options: { cursor?: string | null; limit?: number; signal?: AbortSignal } = {},
) {
  const params = new URLSearchParams();
  if (options.cursor) params.set('cursor', options.cursor);
  if (options.limit) params.set('limit', String(options.limit));
  const query = params.size > 0 ? `?${params.toString()}` : '';
  return api<ChatMessagePage>(
    `/chat/agents/${encodeURIComponent(agentKey)}/messages${query}`,
    { signal: options.signal },
  );
}

export function sendChatMessage(agentKey: string, payload: SendChatMessageRequest) {
  return api<SendChatMessageResponse>(
    `/chat/agents/${encodeURIComponent(agentKey)}/messages`,
    { method: 'POST', body: payload },
  );
}

export function chatEventSourceUrl(agentKey: string) {
  return `/api/v1/chat/agents/${encodeURIComponent(agentKey)}/events`;
}

export function parseChatEvent(value: string): ChatEvent | null {
  try {
    const payload: unknown = JSON.parse(value);
    if (!payload || typeof payload !== 'object') return null;
    const candidate = payload as Partial<ChatEvent>;
    if (
      typeof candidate.event !== 'string'
      || typeof candidate.agent_key !== 'string'
    ) {
      return null;
    }
    return candidate as ChatEvent;
  } catch {
    return null;
  }
}

export function beginChatAuthorization(agentKey: string) {
  return api<ChatAuthorizeResponse>(
    `/chat/agents/${encodeURIComponent(agentKey)}/authorize`,
  );
}

export function completeChatAuthorization(code: string, state: string) {
  return api<ChatOAuthCallbackResponse>('/chat/feishu/callback', {
    method: 'POST',
    body: { code, state },
  });
}

export function disconnectChatAuthorization(agentKey: string) {
  return api<ChatDisconnectResponse>(
    `/chat/agents/${encodeURIComponent(agentKey)}/disconnect`,
    { method: 'POST' },
  );
}
