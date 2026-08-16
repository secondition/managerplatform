import { AgentSidebar, MobileAgentPicker } from './AgentSidebar';
import ChatComposer from './ChatComposer';
import ChatHeader from './ChatHeader';
import { buildChatViewModel } from './chatState';
import ChatStatePanel from './ChatStatePanel';
import ChatStatusBanner from './ChatStatusBanner';
import MessageList from './MessageList';
import type {
  AssistantFileMessage,
  ChatAgentStatus,
  ChatAgentSummary,
  ChatDisplayMessage,
  ChatMessageListViewState,
} from './types';

interface ChatWorkspaceProps {
  agents: ChatAgentSummary[];
  selectedAgent: ChatAgentSummary | null;
  selectedStatus: ChatAgentStatus | null;
  messages: ChatDisplayMessage[];
  messageList: ChatMessageListViewState;
  composerSubmitting?: boolean;
  actionPending?: boolean;
  helperText?: string;
  onSelectAgent: (agentKey: string) => void;
  onAuthorize?: () => void;
  onSubmit?: (text: string) => boolean | void;
  onLoadMore?: () => void;
  onRetryLoad?: () => void;
  onRetryMessage?: (message: ChatDisplayMessage) => void;
  onAttachmentAction?: (message: AssistantFileMessage) => void;
}

export default function ChatWorkspace({
  agents,
  selectedAgent,
  selectedStatus,
  messages,
  messageList,
  composerSubmitting = false,
  actionPending = false,
  helperText,
  onSelectAgent,
  onAuthorize,
  onSubmit,
  onLoadMore,
  onRetryLoad,
  onRetryMessage,
  onAttachmentAction,
}: ChatWorkspaceProps) {
  const selectedAgentKey = selectedAgent?.agent_key ?? null;
  const view = buildChatViewModel(agents, selectedAgent, selectedStatus);

  return (
    <section className="workspace-card flex min-h-0 flex-1 overflow-hidden" aria-label="AI 大脑工作区">
      {agents.length > 0 ? (
        <AgentSidebar
          agents={agents}
          selectedAgentKey={selectedAgentKey}
          onSelect={onSelectAgent}
        />
      ) : null}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-white">
        {agents.length > 0 ? (
          <MobileAgentPicker
            agents={agents}
            selectedAgentKey={selectedAgentKey}
            onSelect={onSelectAgent}
          />
        ) : null}
        <ChatHeader agent={selectedAgent} />
        {view.banner ? <ChatStatusBanner banner={view.banner} /> : null}
        {view.showStatePanel ? (
          <ChatStatePanel
            view={view}
            onAction={onAuthorize}
            actionPending={actionPending}
          />
        ) : null}
        {view.showMessages && selectedAgent ? (
          <MessageList
            agent={selectedAgent}
            messages={messages}
            listState={messageList}
            onLoadMore={onLoadMore}
            onRetryLoad={onRetryLoad}
            onRetryMessage={onRetryMessage}
            onAttachmentAction={onAttachmentAction}
          />
        ) : null}
        {view.showComposer ? (
          <ChatComposer
            disabled={view.composerDisabled}
            placeholder={view.composerPlaceholder}
            disabledHint={view.composerHint}
            helperText={helperText}
            draftKey={selectedAgentKey ?? undefined}
            submitting={composerSubmitting}
            onSubmit={onSubmit}
          />
        ) : null}
      </div>
    </section>
  );
}
