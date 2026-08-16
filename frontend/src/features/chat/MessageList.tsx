import {
  CircleAlert,
  LoaderCircle,
  LockKeyhole,
  MessagesSquare,
  RefreshCw,
} from 'lucide-react';
import { useLayoutEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';
import type {
  AssistantFileMessage,
  ChatAgentSummary,
  ChatDisplayMessage,
  ChatMessageListViewState,
} from './types';

interface MessageListProps {
  agent: ChatAgentSummary;
  messages: ChatDisplayMessage[];
  listState: ChatMessageListViewState;
  onLoadMore?: () => void;
  onRetryLoad?: () => void;
  onRetryMessage?: (message: ChatDisplayMessage) => void;
  onAttachmentAction?: (message: AssistantFileMessage) => void;
}

export default function MessageList({
  agent,
  messages,
  listState,
  onLoadMore,
  onRetryLoad,
  onRetryMessage,
  onAttachmentAction,
}: MessageListProps) {
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const previousMessagesRef = useRef({
    agentKey: '',
    firstId: null as string | null,
    lastId: null as string | null,
    scrollHeight: 0,
    initialized: false,
    nearBottom: true,
  });

  useLayoutEffect(() => {
    const container = scrollContainerRef.current;
    if (!container || messages.length === 0) return;

    const previous = previousMessagesRef.current;
    const firstId = messages[0]?.id ?? null;
    const lastId = messages.at(-1)?.id ?? null;
    const agentChanged = previous.agentKey !== agent.agent_key;
    const historyPrepended = !agentChanged
      && previous.initialized
      && previous.firstId !== firstId
      && previous.lastId === lastId;
    const messageAppended = !agentChanged
      && previous.initialized
      && previous.lastId !== lastId;

    if (agentChanged || !previous.initialized) {
      container.scrollTop = container.scrollHeight;
    } else if (historyPrepended) {
      container.scrollTop += container.scrollHeight - previous.scrollHeight;
    } else if (messageAppended && previous.nearBottom) {
      container.scrollTop = container.scrollHeight;
    }

    previousMessagesRef.current = {
      agentKey: agent.agent_key,
      firstId,
      lastId,
      scrollHeight: container.scrollHeight,
      initialized: true,
      nearBottom: isNearBottom(container),
    };
  }, [agent.agent_key, messages]);

  if (listState.status === 'loading' && messages.length === 0) {
    return <MessageListSkeleton />;
  }

  if (listState.status === 'error' && messages.length === 0) {
    return (
      <MessageListFailure
        message={listState.error_message ?? '聊天记录加载失败，请稍后再试。'}
        onRetry={onRetryLoad}
      />
    );
  }

  if (messages.length === 0) {
    return <EmptyConversation agent={agent} />;
  }

  return (
    <div
      ref={scrollContainerRef}
      className="min-h-0 flex-1 overscroll-contain overflow-y-auto px-4 py-5 sm:px-6"
      aria-label="消息列表"
      aria-busy={listState.status === 'loading_more'}
      onScroll={(event) => {
        previousMessagesRef.current.nearBottom = isNearBottom(event.currentTarget);
      }}
    >
      <div className="mx-auto max-w-3xl space-y-4">
        <MessageHistoryControl
          listState={listState}
          onLoadMore={onLoadMore}
          onRetry={onRetryLoad}
        />

        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            agent={agent}
            message={message}
            onRetry={onRetryMessage}
            onAttachmentAction={onAttachmentAction}
          />
        ))}
      </div>
    </div>
  );
}

function isNearBottom(container: HTMLDivElement) {
  return container.scrollHeight - container.scrollTop - container.clientHeight < 120;
}

function MessageHistoryControl({
  listState,
  onLoadMore,
  onRetry,
}: {
  listState: ChatMessageListViewState;
  onLoadMore?: () => void;
  onRetry?: () => void;
}) {
  if (listState.status === 'loading_more') {
    return (
      <div className="flex items-center justify-center gap-1.5 py-1 text-[10px] text-slate-400" role="status">
        <LoaderCircle size={12} className="animate-spin" /> 正在加载更早的消息…
      </div>
    );
  }

  if (listState.status === 'error') {
    return (
      <div className="flex flex-wrap items-center justify-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[10px] text-rose-600" role="alert">
        <CircleAlert size={12} />
        <span>{listState.error_message ?? '更早的聊天记录加载失败。'}</span>
        <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 font-medium hover:text-rose-800">
          <RefreshCw size={10} /> 重试
        </button>
      </div>
    );
  }

  if (listState.has_more) {
    return (
      <div className="text-center">
        <button
          type="button"
          onClick={onLoadMore}
          className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[10px] text-slate-500 hover:border-[var(--theme-accent)] hover:text-[var(--theme-accent)]"
        >
          查看更早的消息
        </button>
      </div>
    );
  }

  return <p className="text-center text-[9px] text-slate-300">已展示当前同步范围内的全部消息</p>;
}

function EmptyConversation({ agent }: { agent: ChatAgentSummary }) {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto px-5 py-10">
      <div className="max-w-md text-center">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]">
          <MessagesSquare size={24} />
        </span>
        <h3 className="mt-4 text-sm font-semibold text-slate-800">开始与{agent.name}对话</h3>
        <p className="mt-2 text-[11px] leading-5 text-slate-400">
          发送第一条消息后，对话会通过飞书安全群形成个人消息投影，并按时间显示在这里。
        </p>
        <div className="mt-5 inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[10px] text-slate-400">
          <LockKeyhole size={11} /> 其他群成员的消息不会展示在这里
        </div>
      </div>
    </div>
  );
}

function MessageListFailure({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto px-5 py-10" role="alert">
      <div className="max-w-md text-center">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-50 text-rose-600">
          <CircleAlert size={24} />
        </span>
        <h3 className="mt-4 text-sm font-semibold text-slate-800">聊天记录加载失败</h3>
        <p className="mt-2 text-[11px] leading-5 text-slate-500">{message}</p>
        <button type="button" onClick={onRetry} className="workspace-button mt-5">
          <RefreshCw size={12} /> 重新加载
        </button>
      </div>
    </div>
  );
}

function MessageListSkeleton() {
  return (
    <div className="min-h-0 flex-1 overflow-hidden px-4 py-5 sm:px-6" aria-label="正在加载聊天记录" aria-busy="true">
      <div className="mx-auto max-w-3xl space-y-5">
        <p className="flex items-center justify-center gap-1.5 text-[10px] text-slate-400">
          <LoaderCircle size={12} className="animate-spin" /> 正在加载聊天记录…
        </p>
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className={`flex ${item % 2 === 0 ? 'justify-end' : 'justify-start'}`}>
            <div className={`animate-pulse rounded-2xl bg-slate-100 ${item % 2 === 0 ? 'h-14 w-[48%]' : 'h-20 w-[64%]'}`} />
          </div>
        ))}
      </div>
    </div>
  );
}
