import type {
  ChatAgentStatus,
  ChatAgentSummary,
  ChatPageState,
  ChatStateTone,
} from './types';

export interface ChatStateAction {
  label: string;
}

export interface ChatStateBanner {
  title: string;
  description: string;
  tone: ChatStateTone;
}

export interface ChatViewModel {
  state: ChatPageState;
  title: string;
  description: string;
  tone: ChatStateTone;
  headerLabel: string;
  showStatePanel: boolean;
  showMessages: boolean;
  showComposer: boolean;
  composerDisabled: boolean;
  composerPlaceholder: string;
  composerHint: string | null;
  action: ChatStateAction | null;
  banner: ChatStateBanner | null;
}

const STATE_COPY: Record<
  ChatPageState,
  Pick<ChatViewModel, 'title' | 'description' | 'tone' | 'headerLabel'>
> = {
  no_agents: {
    title: '当前没有可用的智能体',
    description: '你仍然可以进入 AI 大脑。管理员为你开放智能体后，它会自动出现在这里。',
    tone: 'neutral',
    headerLabel: '暂无智能体',
  },
  authorization_required: {
    title: '启用查宝后开始对话',
    description: '需要补充飞书消息发送授权，授权只用于以你本人身份向查宝安全群发送消息。',
    tone: 'info',
    headerLabel: '需要授权',
  },
  not_chat_member: {
    title: '你暂不在查宝安全群中',
    description: '平台开放范围不能绕过飞书群成员边界。加入对应安全群后才能查看和发送消息。',
    tone: 'warning',
    headerLabel: '无群成员资格',
  },
  membership_unknown: {
    title: '正在核验飞书群成员资格',
    description: '成员信息尚未完成同步。为避免越权，核验完成前不会展示聊天记录或开放输入。',
    tone: 'info',
    headerLabel: '资格核验中',
  },
  membership_stale: {
    title: '成员信息需要重新确认',
    description: '最近一次群成员快照已超过可信时限，系统已按安全策略临时限制访问。',
    tone: 'warning',
    headerLabel: '资格待更新',
  },
  backfilling: {
    title: '正在准备最近的对话记录',
    description: '系统正在同步最近 30 天的群消息并建立个人投影，完成后会自动开放对话。',
    tone: 'info',
    headerLabel: '初始同步中',
  },
  sync_delayed: {
    title: '消息同步存在延迟',
    description: '你可以继续对话，但新消息可能需要更长时间才会出现在网页中。',
    tone: 'warning',
    headerLabel: '同步延迟',
  },
  sync_blocked: {
    title: '消息服务暂不可用',
    description: '群消息同步当前被阻塞。系统恢复前不会展示可能不完整的记录，也不会发送新消息。',
    tone: 'danger',
    headerLabel: '同步已阻塞',
  },
  ready: {
    title: '开始与查宝协作',
    description: '这里仅展示属于当前账号的消息投影，其他群成员的消息不会出现在网页中。',
    tone: 'success',
    headerLabel: '运行正常',
  },
  maintenance: {
    title: '查宝正在维护',
    description: '聊天能力暂时关闭，维护期间不会读取或发送新消息，请稍后再试。',
    tone: 'neutral',
    headerLabel: '维护中',
  },
};

export const chatAvailabilityLabels: Record<ChatPageState, string> = Object.fromEntries(
  Object.entries(STATE_COPY).map(([state, copy]) => [state, copy.headerLabel]),
) as Record<ChatPageState, string>;

export function buildChatViewModel(
  agents: ChatAgentSummary[],
  selectedAgent: ChatAgentSummary | null,
  status: ChatAgentStatus | null,
): ChatViewModel {
  const state = resolvePageState(agents, selectedAgent, status);
  const copy = STATE_COPY[state];
  const supportsConversation = state === 'ready' || state === 'sync_delayed';
  const showMessages = supportsConversation && status?.can_read === true;
  const showComposer = supportsConversation && status?.can_read === true;
  const composerDisabled = status?.can_send !== true;

  return {
    state,
    ...copy,
    showStatePanel: !supportsConversation,
    showMessages,
    showComposer,
    composerDisabled,
    composerPlaceholder: composerDisabled
      ? '当前状态下暂不能发送消息'
      : `向${selectedAgent?.name ?? '智能体'}发送消息`,
    composerHint: composerDisabled ? '发送权限当前不可用' : null,
    action:
      state === 'authorization_required'
        ? {
            label: '启用查宝',
          }
        : null,
    banner: state === 'sync_delayed' ? buildDelayedBanner(status) : null,
  };
}

function resolvePageState(
  agents: ChatAgentSummary[],
  selectedAgent: ChatAgentSummary | null,
  status: ChatAgentStatus | null,
): ChatPageState {
  if (agents.length === 0) return 'no_agents';
  if (!selectedAgent || !status) return 'maintenance';
  return selectedAgent.status;
}

function buildDelayedBanner(status: ChatAgentStatus | null): ChatStateBanner {
  const syncTime = status?.last_sync_at ? formatTime(status.last_sync_at) : '未知时间';
  const delay = status?.sync_delay_seconds
    ? `，当前延迟约 ${formatDuration(status.sync_delay_seconds)}`
    : '';

  return {
    title: '消息同步存在延迟',
    description: `当前展示截至 ${syncTime} 的数据${delay}，发送后的新消息可能稍后出现。`,
    tone: 'warning',
  };
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '未知时间';
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

function formatDuration(seconds: number) {
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return remainingSeconds > 0 ? `${minutes} 分 ${remainingSeconds} 秒` : `${minutes} 分钟`;
}
