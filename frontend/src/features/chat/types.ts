export type ChatImplementationType = 'feishu_group_projection';

export type ChatAgentAvailability =
  | 'authorization_required'
  | 'not_chat_member'
  | 'membership_unknown'
  | 'membership_stale'
  | 'backfilling'
  | 'sync_delayed'
  | 'sync_blocked'
  | 'ready'
  | 'maintenance';

export type ChatPageState = 'no_agents' | ChatAgentAvailability;

export type ChatStateTone = 'neutral' | 'info' | 'warning' | 'danger' | 'success';

export type ChatCredentialStatus =
  | 'active'
  | 'authorization_required'
  | 'refreshing'
  | 'revoked';

export type ChatMembershipStatus = 'active' | 'not_member' | 'unknown' | 'stale';

export type ChatSyncStatus =
  | 'disabled'
  | 'backfilling'
  | 'healthy'
  | 'delayed'
  | 'rate_limited'
  | 'blocked';

export interface ChatAgentSummary {
  agent_key: string;
  name: string;
  description: string;
  avatar_url: string | null;
  implementation_type: ChatImplementationType;
  platform_granted: boolean;
  status: ChatAgentAvailability;
}

export interface ChatAgentStatus {
  agent_key: string;
  platform_granted: boolean;
  credential_status: ChatCredentialStatus;
  membership_status: ChatMembershipStatus;
  sync_status: ChatSyncStatus;
  can_read: boolean;
  can_send: boolean;
  blocked_reason: string | null;
  last_sync_at: string | null;
  sync_delay_seconds: number | null;
}

export interface ChatScenarioData {
  agents: ChatAgentSummary[];
  statuses: Record<string, ChatAgentStatus>;
  messages: ChatDisplayMessage[];
  message_list: ChatMessageListViewState;
}

interface ChatMessageBase {
  id: string;
  created_at: string;
}

export interface UserTextMessage extends ChatMessageBase {
  role: 'user';
  kind: 'user_text';
  body_text: string;
  client_request_id?: string;
}

export interface AssistantMarkdownMessage extends ChatMessageBase {
  role: 'assistant';
  kind: 'assistant_markdown';
  body_markdown: string;
}

export type AttachmentDownloadStatus =
  | 'available'
  | 'preparing'
  | 'too_large'
  | 'unavailable'
  | 'view_in_feishu';

export interface AssistantFileMessage extends ChatMessageBase {
  role: 'assistant';
  kind: 'assistant_file';
  file_name: string;
  file_type: string | null;
  file_size: number | null;
  download_status: AttachmentDownloadStatus;
  download_url: string | null;
}

export interface UnsupportedChatMessage extends ChatMessageBase {
  role: 'assistant';
  kind: 'unsupported';
  label: string;
}

export type ChatMessage =
  | UserTextMessage
  | AssistantMarkdownMessage
  | AssistantFileMessage
  | UnsupportedChatMessage;

export type ChatMessageDeliveryState = 'sending' | 'sent' | 'failed';

export type ChatDisplayMessage = ChatMessage & {
  delivery_state?: ChatMessageDeliveryState;
  delivery_error?: string | null;
};

export type ChatMessageListStatus = 'loading' | 'ready' | 'loading_more' | 'error';

export interface ChatMessageListViewState {
  status: ChatMessageListStatus;
  has_more: boolean;
  error_message: string | null;
}

export interface ChatMessagePage {
  items: ChatMessage[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface SendChatMessageRequest {
  text: string;
  client_request_id: string;
}

export type SendChatMessageStatus =
  | 'sending'
  | 'sent_to_feishu'
  | 'synced'
  | 'failed';

export interface SendChatMessageResponse {
  client_request_id: string;
  status: SendChatMessageStatus;
  message_id: string | null;
  error_code: string | null;
  error_message: string | null;
}

export type ChatEventType =
  | 'ready'
  | 'message.created'
  | 'message.updated'
  | 'message.deleted'
  | 'agent.access_revoked'
  | 'authorization.required'
  | 'sync.delayed'
  | 'heartbeat';

export interface ChatEvent {
  event: ChatEventType;
  agent_key: string;
  event_id?: string;
  cursor_hint?: string;
}
