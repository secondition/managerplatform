import { Bot, CircleAlert, LoaderCircle, RotateCcw } from 'lucide-react';
import { lazy, Suspense } from 'react';
import AttachmentCard from './AttachmentCard';
import type {
  AssistantFileMessage,
  ChatAgentSummary,
  ChatDisplayMessage,
} from './types';

const MarkdownMessage = lazy(() => import('./MarkdownMessage'));

interface MessageBubbleProps {
  agent: ChatAgentSummary;
  message: ChatDisplayMessage;
  onRetry?: (message: ChatDisplayMessage) => void;
  onAttachmentAction?: (message: AssistantFileMessage) => void;
}

export default function MessageBubble({
  agent,
  message,
  onRetry,
  onAttachmentAction,
}: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isFile = message.kind === 'assistant_file';

  return (
    <article className={`flex gap-2.5 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser ? (
        <span
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]"
          aria-label={agent.name}
        >
          <Bot size={15} />
        </span>
      ) : null}

      <div className={`${isFile ? 'max-w-[92%] sm:max-w-[82%]' : 'max-w-[84%] sm:max-w-[74%]'} ${isUser ? 'text-right' : ''}`}>
        <div
          className={isFile
            ? 'text-left'
            : `rounded-2xl px-3.5 py-2.5 text-left text-[12px] leading-5 ${
                isUser
                  ? 'rounded-br-md bg-[var(--theme-accent)] text-white'
                  : 'rounded-bl-md border border-slate-200 bg-slate-50 text-slate-700'
              }`}
        >
          <MessageBody message={message} onAttachmentAction={onAttachmentAction} />
        </div>
        <MessageMeta message={message} onRetry={onRetry} />
      </div>
    </article>
  );
}

function MessageBody({
  message,
  onAttachmentAction,
}: {
  message: ChatDisplayMessage;
  onAttachmentAction?: (message: AssistantFileMessage) => void;
}) {
  if (message.kind === 'user_text') {
    return <p className="whitespace-pre-wrap break-words">{message.body_text}</p>;
  }

  if (message.kind === 'assistant_markdown') {
    return (
      <Suspense fallback={<p className="whitespace-pre-wrap break-words">{message.body_markdown}</p>}>
        <MarkdownMessage source={message.body_markdown} />
      </Suspense>
    );
  }

  if (message.kind === 'assistant_file') {
    return <AttachmentCard message={message} onAction={onAttachmentAction} />;
  }

  return (
    <div className="flex items-start gap-2 text-slate-500">
      <CircleAlert size={14} className="mt-0.5 shrink-0" />
      <p>{message.label}</p>
    </div>
  );
}

function MessageMeta({
  message,
  onRetry,
}: {
  message: ChatDisplayMessage;
  onRetry?: (message: ChatDisplayMessage) => void;
}) {
  const time = formatMessageTime(message.created_at);

  return (
    <div className={`mt-1 flex min-h-4 items-center gap-1.5 px-1 text-[9px] ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <time className="text-slate-300" dateTime={message.created_at}>{time}</time>
      {message.delivery_state === 'sending' ? (
        <span className="inline-flex items-center gap-1 text-slate-400">
          <LoaderCircle size={9} className="animate-spin" /> 发送中
        </span>
      ) : null}
      {message.delivery_state === 'sent' ? (
        <span className="text-slate-400">已发送</span>
      ) : null}
      {message.delivery_state === 'failed' ? (
        <span className="inline-flex flex-wrap items-center justify-end gap-1 text-rose-500">
          <CircleAlert size={9} /> {message.delivery_error ?? '发送失败'}
          <button
            type="button"
            onClick={() => onRetry?.(message)}
            className="inline-flex items-center gap-0.5 font-medium hover:text-rose-700"
          >
            <RotateCcw size={9} /> 重试
          </button>
        </span>
      ) : null}
    </div>
  );
}

function formatMessageTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}
