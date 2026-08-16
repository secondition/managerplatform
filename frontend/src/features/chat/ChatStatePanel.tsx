import {
  Bot,
  History,
  KeyRound,
  LoaderCircle,
  ShieldAlert,
  TriangleAlert,
  UserRoundX,
  Wrench,
} from 'lucide-react';
import type { ChatViewModel } from './chatState';
import type { ChatPageState } from './types';

interface ChatStatePanelProps {
  view: ChatViewModel;
  onAction?: () => void;
  actionPending?: boolean;
}

const TONE_CLASSES = {
  neutral: 'bg-slate-100 text-slate-500',
  info: 'bg-blue-50 text-blue-600',
  warning: 'bg-amber-50 text-amber-600',
  danger: 'bg-rose-50 text-rose-600',
  success: 'bg-emerald-50 text-emerald-600',
};

const STATE_ICONS = {
  no_agents: Bot,
  authorization_required: KeyRound,
  not_chat_member: UserRoundX,
  membership_unknown: ShieldAlert,
  membership_stale: ShieldAlert,
  backfilling: LoaderCircle,
  sync_delayed: History,
  sync_blocked: TriangleAlert,
  ready: Bot,
  maintenance: Wrench,
} satisfies Record<ChatPageState, typeof Bot>;

export default function ChatStatePanel({
  view,
  onAction,
  actionPending = false,
}: ChatStatePanelProps) {
  const Icon = STATE_ICONS[view.state];

  return (
    <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto px-5 py-10">
      <div className="max-w-md text-center">
        <span className={`mx-auto flex h-14 w-14 items-center justify-center rounded-2xl ${TONE_CLASSES[view.tone]}`}>
          <Icon size={24} className={view.state === 'backfilling' ? 'animate-spin' : undefined} />
        </span>
        <h3 className="mt-4 text-sm font-semibold text-slate-800">{view.title}</h3>
        <p className="mt-2 text-[11px] leading-5 text-slate-500">{view.description}</p>

        {view.action ? (
          <div className="mt-5">
            <button
              type="button"
              className="workspace-button workspace-button-primary"
              onClick={onAction}
              disabled={actionPending}
            >
              {actionPending ? <LoaderCircle size={12} className="animate-spin" /> : null}
              {actionPending ? '正在打开授权页…' : view.action.label}
            </button>
          </div>
        ) : null}

      </div>
    </div>
  );
}
