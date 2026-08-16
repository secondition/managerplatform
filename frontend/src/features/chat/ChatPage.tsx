import {
  BrainCircuit,
  CircleAlert,
  LoaderCircle,
  RefreshCw,
} from 'lucide-react';
import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import ChatWorkspace from './ChatWorkspace';
import type {
  ChatMockMessageView,
  ChatMockMessageViewKey,
  ChatMockScenario,
  ChatMockScenarioKey,
} from './mock/mockScenarios';
import type {
  AssistantFileMessage,
  ChatDisplayMessage,
  ChatMessageListViewState,
} from './types';
import { useLiveChat } from './useLiveChat';

const DEFAULT_DEVELOPMENT_SCENARIO: ChatMockScenarioKey = 'no_agents';
const DEFAULT_MESSAGE_VIEW: ChatMockMessageViewKey = 'showcase';

const PREVIEW_SCENARIOS = new Set<ChatMockScenarioKey>([
  'no_agents',
  'authorization_required',
  'not_chat_member',
  'membership_unknown',
  'membership_stale',
  'backfilling',
  'sync_delayed',
  'sync_blocked',
  'ready',
  'maintenance',
]);

const DevelopmentScenarioPicker = import.meta.env.DEV
  ? lazy(() => import('./mock/MockScenarioPicker'))
  : null;

export default function ChatPage() {
  const [searchParams] = useSearchParams();
  const requestedScenario = searchParams.get('scenario');
  const previewMode = import.meta.env.DEV
    && requestedScenario !== null
    && PREVIEW_SCENARIOS.has(requestedScenario as ChatMockScenarioKey);

  return previewMode ? <DevelopmentChatPreview /> : <LiveChatPage />;
}

function LiveChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedAgentKey = searchParams.get('agent');
  const chat = useLiveChat(requestedAgentKey, true);

  useEffect(() => {
    if (!chat.selectedAgentKey || chat.selectedAgentKey === requestedAgentKey) return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('agent', chat.selectedAgentKey);
    setSearchParams(nextParams, { replace: true });
  }, [chat.selectedAgentKey, requestedAgentKey, searchParams, setSearchParams]);

  function handleSelectAgent(agentKey: string) {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('agent', agentKey);
    setSearchParams(nextParams, { replace: true });
    chat.setNotice(null);
  }

  return (
    <div className="workspace-page flex h-[calc(100dvh-var(--app-header-height))] min-h-0 flex-col overflow-hidden">
      <PageHeading />
      {chat.notice ? (
        <PageNotice
          notice={chat.notice}
          onDismiss={() => chat.setNotice(null)}
        />
      ) : null}
      {chat.pageLoading ? (
        <ChatPageLoading />
      ) : chat.pageError ? (
        <ChatPageFailure message={chat.pageError} onRetry={chat.retryBootstrap} />
      ) : (
        <ChatWorkspace
          agents={chat.agents}
          selectedAgent={chat.selectedAgent}
          selectedStatus={chat.selectedStatus}
          messages={chat.messages}
          messageList={chat.messageList}
          composerSubmitting={chat.composerSubmitting}
          actionPending={chat.authorizing}
          helperText={chat.helperText}
          onSelectAgent={handleSelectAgent}
          onAuthorize={chat.authorize}
          onSubmit={chat.submitMessage}
          onLoadMore={chat.loadMore}
          onRetryLoad={chat.retryMessages}
          onRetryMessage={chat.retryMessage}
          onAttachmentAction={chat.attachmentAction}
        />
      )}
    </div>
  );
}

function DevelopmentChatPreview() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [previewNotice, setPreviewNotice] = useState<string | null>(null);
  const [composerSubmitting, setComposerSubmitting] = useState(false);
  const [messageOverrides, setMessageOverrides] = useState<Record<string, ChatDisplayMessage[]>>({});
  const [listStateOverrides, setListStateOverrides] = useState<Record<string, ChatMessageListViewState>>({});
  const previewTimers = useRef<number[]>([]);
  const [developmentScenarios, setDevelopmentScenarios] = useState<Record<
    ChatMockScenarioKey,
    ChatMockScenario
  > | null>(null);
  const [developmentMessageViews, setDevelopmentMessageViews] = useState<Record<
    ChatMockMessageViewKey,
    ChatMockMessageView
  > | null>(null);

  useEffect(() => {
    if (!import.meta.env.DEV) return;

    let active = true;
    void import('./mock/mockScenarios').then(({
      CHAT_MOCK_MESSAGE_VIEWS,
      CHAT_MOCK_SCENARIOS,
    }) => {
      if (active) {
        setDevelopmentScenarios(CHAT_MOCK_SCENARIOS);
        setDevelopmentMessageViews(CHAT_MOCK_MESSAGE_VIEWS);
      }
    });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => () => {
    previewTimers.current.forEach((timer) => window.clearTimeout(timer));
  }, []);

  const requestedScenario = searchParams.get('scenario');
  const scenarioKey = isLoadedScenarioKey(requestedScenario, developmentScenarios)
    ? requestedScenario
    : DEFAULT_DEVELOPMENT_SCENARIO;
  const scenario = import.meta.env.DEV && developmentScenarios
    ? developmentScenarios[scenarioKey]
    : null;
  const requestedMessageView = searchParams.get('messageView');
  const messageViewKey = isLoadedMessageViewKey(requestedMessageView, developmentMessageViews)
    ? requestedMessageView
    : DEFAULT_MESSAGE_VIEW;
  const messageViewEnabled = scenarioKey === 'ready' || scenarioKey === 'sync_delayed';
  const selectedMessageView = import.meta.env.DEV && messageViewEnabled && developmentMessageViews
    ? developmentMessageViews[messageViewKey]
    : null;
  const requestedAgentKey = searchParams.get('agent');
  const selectedAgent = scenario?.agents.find((agent) => agent.agent_key === requestedAgentKey)
    ?? scenario?.agents[0]
    ?? null;
  const selectedAgentKey = selectedAgent?.agent_key ?? null;
  const selectedStatus = selectedAgent ? scenario?.statuses[selectedAgent.agent_key] ?? null : null;
  const previewContextKey = `${scenarioKey}:${selectedAgentKey ?? 'none'}:${messageViewKey}`;
  const baseMessages = selectedMessageView?.messages ?? scenario?.messages ?? [];
  const baseListState = selectedMessageView?.message_list
    ?? scenario?.message_list
    ?? { status: 'loading', has_more: false, error_message: null };
  const displayedMessages = messageOverrides[previewContextKey] ?? baseMessages;
  const displayedListState = listStateOverrides[previewContextKey] ?? baseListState;

  function updateSearchParams(changes: Record<string, string | null>) {
    const nextParams = new URLSearchParams(searchParams);
    Object.entries(changes).forEach(([key, value]) => {
      if (value) nextParams.set(key, value);
      else nextParams.delete(key);
    });
    setSearchParams(nextParams, { replace: true });
  }

  function handleScenarioChange(nextScenario: ChatMockScenarioKey) {
    const nextAgent = developmentScenarios?.[nextScenario].agents[0]?.agent_key ?? null;
    const nextSupportsMessages = nextScenario === 'ready' || nextScenario === 'sync_delayed';
    setPreviewNotice(null);
    setComposerSubmitting(false);
    updateSearchParams({
      scenario: nextScenario,
      agent: nextAgent,
      messageView: nextSupportsMessages ? DEFAULT_MESSAGE_VIEW : null,
    });
  }

  function handleMessageViewChange(nextView: ChatMockMessageViewKey) {
    setPreviewNotice(null);
    setComposerSubmitting(false);
    updateSearchParams({ messageView: nextView });
  }

  function handleSelectAgent(agentKey: string) {
    setPreviewNotice(null);
    updateSearchParams({ agent: agentKey });
  }

  function showPreviewNotice(message: string) {
    setPreviewNotice(message);
  }

  const handleAuthorizationPreview = import.meta.env.DEV
    ? () => showPreviewNotice('当前为前端状态预览，尚未接入飞书增量授权。')
    : undefined;
  const handleMessagePreview = import.meta.env.DEV
    ? (text: string) => {
        const messageId = `preview-${Date.now()}`;
        const optimisticMessage: ChatDisplayMessage = {
          id: messageId,
          role: 'user',
          kind: 'user_text',
          body_text: text,
          created_at: new Date().toISOString(),
          delivery_state: 'sending',
        };

        setMessageOverrides((current) => ({
          ...current,
          [previewContextKey]: [...(current[previewContextKey] ?? displayedMessages), optimisticMessage],
        }));
        setComposerSubmitting(true);
        showPreviewNotice('已生成本地发送状态，本次消息不会离开浏览器。');

        previewTimers.current.push(window.setTimeout(() => {
          updatePreviewMessage(previewContextKey, messageId, { delivery_state: 'sent' });
          setComposerSubmitting(false);
        }, 800));
        return true;
      }
    : undefined;
  const handleRetryMessagePreview = import.meta.env.DEV
    ? (message: ChatDisplayMessage) => {
        updatePreviewMessage(previewContextKey, message.id, {
          delivery_state: 'sending',
          delivery_error: null,
        });
        showPreviewNotice('正在本地模拟重试，不会发起网络请求。');
        previewTimers.current.push(window.setTimeout(() => {
          updatePreviewMessage(previewContextKey, message.id, { delivery_state: 'sent' });
        }, 800));
      }
    : undefined;
  const handleListActionPreview = import.meta.env.DEV
    ? () => {
        setListStateOverrides((current) => ({
          ...current,
          [previewContextKey]: {
            status: displayedMessages.length > 0 ? 'loading_more' : 'loading',
            has_more: displayedMessages.length > 0,
            error_message: null,
          },
        }));
        showPreviewNotice('正在本地模拟历史消息加载，不会发起网络请求。');
        previewTimers.current.push(window.setTimeout(() => {
          setListStateOverrides((current) => ({
            ...current,
            [previewContextKey]: { status: 'ready', has_more: false, error_message: null },
          }));
        }, 800));
      }
    : undefined;
  const handleAttachmentPreview = import.meta.env.DEV
    ? (message: AssistantFileMessage) => {
        showPreviewNotice(`“${message.file_name}”的真实下载或飞书跳转将在后端接入后开放。`);
      }
    : undefined;

  function updatePreviewMessage(
    contextKey: string,
    messageId: string,
    changes: Partial<ChatDisplayMessage>,
  ) {
    setMessageOverrides((current) => ({
      ...current,
      [contextKey]: (current[contextKey] ?? displayedMessages).map((message) =>
        message.id === messageId ? { ...message, ...changes } as ChatDisplayMessage : message,
      ),
    }));
  }

  return (
    <div className="workspace-page flex h-[calc(100dvh-var(--app-header-height))] min-h-0 flex-col overflow-hidden">
      <PageHeading />

      {import.meta.env.DEV && DevelopmentScenarioPicker && developmentScenarios && developmentMessageViews ? (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Suspense fallback={<DevelopmentPreviewLoading />}>
            <DevelopmentScenarioPicker
              value={scenarioKey}
              messageView={messageViewKey}
              messageViewEnabled={messageViewEnabled}
              onChange={handleScenarioChange}
              onMessageViewChange={handleMessageViewChange}
            />
          </Suspense>
          <button
            type="button"
            className="workspace-button"
            onClick={() => updateSearchParams({ scenario: null, messageView: null })}
          >
            返回真实接口
          </button>
        </div>
      ) : null}

      {previewNotice ? (
        <div className="mb-3 rounded-xl border border-blue-200 bg-blue-50 px-3.5 py-2.5 text-[11px] text-blue-700" role="status">
          {previewNotice}
        </div>
      ) : null}

      <ChatWorkspace
        agents={scenario?.agents ?? []}
        selectedAgent={selectedAgent}
        selectedStatus={selectedStatus}
        messages={displayedMessages}
        messageList={displayedListState}
        composerSubmitting={composerSubmitting}
        helperText="Enter 发送，Shift + Enter 换行 · 当前为前端交互预览"
        onSelectAgent={handleSelectAgent}
        onAuthorize={handleAuthorizationPreview}
        onSubmit={handleMessagePreview}
        onLoadMore={handleListActionPreview}
        onRetryLoad={handleListActionPreview}
        onRetryMessage={handleRetryMessagePreview}
        onAttachmentAction={handleAttachmentPreview}
      />
    </div>
  );
}

function PageHeading() {
  return (
    <div className="mb-4 shrink-0">
      <div>
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]">
            <BrainCircuit size={17} />
          </span>
          <h1 className="text-lg font-semibold text-slate-950">AI 大脑</h1>
        </div>
        <p className="mt-1.5 text-[11px] leading-5 text-slate-400">
          汇集企业智能体，在统一、安全的工作空间中完成对话与协作。
        </p>
      </div>
    </div>
  );
}

function PageNotice({
  notice,
  onDismiss,
}: {
  notice: { tone: 'info' | 'error' | 'success'; text: string };
  onDismiss: () => void;
}) {
  const toneClasses = {
    info: 'border-blue-200 bg-blue-50 text-blue-700',
    error: 'border-rose-200 bg-rose-50 text-rose-700',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  };
  return (
    <div
      className={`mb-3 flex items-center justify-between gap-3 rounded-xl border px-3.5 py-2.5 text-[11px] ${toneClasses[notice.tone]}`}
      role={notice.tone === 'error' ? 'alert' : 'status'}
    >
      <span>{notice.text}</span>
      <button type="button" onClick={onDismiss} className="shrink-0 font-medium hover:underline">
        关闭
      </button>
    </div>
  );
}

function ChatPageLoading() {
  return (
    <section className="workspace-card flex min-h-0 flex-1 items-center justify-center" aria-busy="true">
      <p className="inline-flex items-center gap-2 text-xs text-slate-500">
        <LoaderCircle size={15} className="animate-spin" /> 正在加载智能体工作区…
      </p>
    </section>
  );
}

function ChatPageFailure({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section className="workspace-card flex min-h-0 flex-1 items-center justify-center px-5" role="alert">
      <div className="max-w-md text-center">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-50 text-rose-600">
          <CircleAlert size={24} />
        </span>
        <h2 className="mt-4 text-sm font-semibold text-slate-800">AI 大脑加载失败</h2>
        <p className="mt-2 text-[11px] leading-5 text-slate-500">{message}</p>
        <button type="button" onClick={onRetry} className="workspace-button mt-5">
          <RefreshCw size={12} /> 重新加载
        </button>
      </div>
    </section>
  );
}

function isLoadedMessageViewKey(
  value: string | null,
  views: Record<ChatMockMessageViewKey, ChatMockMessageView> | null,
): value is ChatMockMessageViewKey {
  return value !== null && views !== null && Object.hasOwn(views, value);
}

function isLoadedScenarioKey(
  value: string | null,
  scenarios: Record<ChatMockScenarioKey, ChatMockScenario> | null,
): value is ChatMockScenarioKey {
  return value !== null && scenarios !== null && Object.hasOwn(scenarios, value);
}

function DevelopmentPreviewLoading() {
  return (
    <div className="rounded-xl border border-dashed border-violet-200 bg-violet-50/70 px-3 py-2.5 text-[10px] text-violet-600">
      正在加载前端状态预览…
    </div>
  );
}
