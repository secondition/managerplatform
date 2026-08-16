import { ArrowUp, Paperclip } from 'lucide-react';
import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react';

const MAX_MESSAGE_LENGTH = 2000;

interface ChatComposerProps {
  disabled?: boolean;
  placeholder: string;
  disabledHint?: string | null;
  helperText?: string;
  draftKey?: string;
  submitting?: boolean;
  onSubmit?: (text: string) => boolean | void;
}

export default function ChatComposer({
  disabled = true,
  placeholder,
  disabledHint,
  helperText,
  draftKey,
  submitting = false,
  onSubmit,
}: ChatComposerProps) {
  const [draft, setDraft] = useState('');
  const composingRef = useRef(false);
  const normalizedDraft = draft.trim();
  const canSubmit = !disabled && !submitting && normalizedDraft.length > 0;
  const approachingLimit = draft.length >= MAX_MESSAGE_LENGTH * 0.8;

  useEffect(() => {
    setDraft('');
  }, [draftKey]);

  function submitDraft() {
    if (!canSubmit) return;
    const accepted = onSubmit?.(normalizedDraft);
    if (accepted !== false) setDraft('');
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitDraft();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey || composingRef.current || event.nativeEvent.isComposing) return;
    event.preventDefault();
    submitDraft();
  }

  return (
    <footer className="shrink-0 border-t border-slate-200/80 bg-white px-3 py-3 sm:px-5 sm:py-4">
      <form
        onSubmit={handleSubmit}
        className={`mx-auto max-w-3xl rounded-2xl border bg-slate-50/70 p-2 shadow-[0_4px_16px_rgba(15,23,42,0.035)] ${
          disabled ? 'border-slate-200 opacity-80' : 'border-slate-200 focus-within:border-[var(--theme-accent)] focus-within:ring-3 focus-within:ring-[var(--theme-accent-ring)]'
        }`}
      >
        <textarea
          disabled={disabled || submitting}
          value={draft}
          maxLength={MAX_MESSAGE_LENGTH}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => { composingRef.current = true; }}
          onCompositionEnd={() => { composingRef.current = false; }}
          rows={2}
          aria-label="消息输入框"
          aria-describedby="chat-composer-hint"
          placeholder={submitting ? '正在发送消息…' : placeholder}
          className="block max-h-36 min-h-12 w-full resize-none bg-transparent px-2 py-1.5 text-xs leading-5 text-slate-700 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
        />
        <div className="mt-1 flex items-center justify-between gap-3 px-1">
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              disabled
              className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-lg px-2 text-[10px] text-slate-300 disabled:cursor-not-allowed"
              title="第一版暂不支持上传附件"
            >
              <Paperclip size={13} /> 附件暂未开放
            </button>
            {approachingLimit ? (
              <span className={`text-[9px] ${draft.length === MAX_MESSAGE_LENGTH ? 'text-rose-500' : 'text-slate-400'}`}>
                {draft.length}/{MAX_MESSAGE_LENGTH}
              </span>
            ) : null}
          </div>
          <button
            type="submit"
            disabled={!canSubmit}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--theme-accent)] text-white disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
            aria-label={submitting ? '正在发送消息' : '发送消息'}
            title="Enter 发送，Shift + Enter 换行"
          >
            <ArrowUp size={15} />
          </button>
        </div>
      </form>
      <p id="chat-composer-hint" className="mt-2 text-center text-[9px] text-slate-300">
        {disabledHint ?? helperText ?? 'Enter 发送，Shift + Enter 换行 · AI 输出仅供工作参考'}
      </p>
    </footer>
  );
}
