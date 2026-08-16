import type {
  ChatAgentAvailability,
  ChatAgentStatus,
  ChatAgentSummary,
  ChatDisplayMessage,
  ChatMessageListViewState,
  ChatScenarioData,
} from '../types';

export type ChatMockScenarioKey =
  | 'no_agents'
  | ChatAgentAvailability;

export interface ChatMockScenario extends ChatScenarioData {
  key: ChatMockScenarioKey;
  label: string;
  description: string;
}

export type ChatMockMessageViewKey =
  | 'showcase'
  | 'empty'
  | 'loading'
  | 'error'
  | 'loading_more'
  | 'send_states';

export interface ChatMockMessageView {
  key: ChatMockMessageViewKey;
  label: string;
  description: string;
  messages: ChatDisplayMessage[];
  message_list: ChatMessageListViewState;
}

const CHABAO_AGENT: Omit<ChatAgentSummary, 'status'> = {
  agent_key: 'chabao',
  name: '查宝',
  description: '企业数据查询与经营分析助手',
  avatar_url: null,
  implementation_type: 'feishu_group_projection',
  platform_granted: true,
};

const READY_MESSAGES: ChatDisplayMessage[] = [
  {
    id: 'mock-user-1',
    role: 'user',
    kind: 'user_text',
    body_text: '帮我汇总昨天各渠道的销售额，并标记异常波动。',
    created_at: '2026-08-12T09:20:00+08:00',
  },
  {
    id: 'mock-assistant-1',
    role: 'assistant',
    kind: 'assistant_markdown',
    body_markdown: `## 昨日经营概览

整体销售额较前一日增长 **8.4%**，建议重点关注以下渠道：

1. 华东直营：退款金额异常增加
2. 华南分销：客单价下降
3. 线上企业购：大额订单集中

| 渠道 | 销售额 | 环比 | 风险 |
| --- | ---: | ---: | --- |
| 华东直营 | ¥1,286,400 | +12.6% | 高 |
| 华南分销 | ¥803,200 | -6.2% | 中 |

可使用 \`order_date\` 字段进一步核验：

\`\`\`sql
SELECT channel, SUM(amount)
FROM sales_orders
GROUP BY channel;
\`\`\`

[查看经营规则说明](https://example.com/rules) · [危险链接会被阻止](javascript:alert('blocked'))

![远程图片不会自动加载](https://example.com/tracker.png)

<img src=x onerror=alert('blocked')>`,
    created_at: '2026-08-12T09:20:08+08:00',
  },
  {
    id: 'mock-user-2',
    role: 'user',
    kind: 'user_text',
    body_text: '把需要关注的渠道列出来。',
    created_at: '2026-08-12T09:21:12+08:00',
  },
  {
    id: 'mock-assistant-2',
    role: 'assistant',
    kind: 'assistant_markdown',
    body_markdown: '> 建议先核对华东直营的退款单，再确认线上企业购的大额订单是否属于正常集中采购。',
    created_at: '2026-08-12T09:21:19+08:00',
  },
  {
    id: 'mock-file-available',
    role: 'assistant',
    kind: 'assistant_file',
    file_name: '昨日渠道销售汇总.xlsx',
    file_type: 'xlsx',
    file_size: 248_320,
    download_status: 'available',
    download_url: null,
    created_at: '2026-08-12T09:21:32+08:00',
  },
  {
    id: 'mock-file-preparing',
    role: 'assistant',
    kind: 'assistant_file',
    file_name: '异常订单明细.xlsx',
    file_type: 'xlsx',
    file_size: 1_438_720,
    download_status: 'preparing',
    download_url: null,
    created_at: '2026-08-12T09:21:35+08:00',
  },
  {
    id: 'mock-file-too-large',
    role: 'assistant',
    kind: 'assistant_file',
    file_name: '年度交易完整明细.xlsx',
    file_type: 'xlsx',
    file_size: 86_240_110,
    download_status: 'too_large',
    download_url: null,
    created_at: '2026-08-12T09:21:38+08:00',
  },
  {
    id: 'mock-file-unavailable',
    role: 'assistant',
    kind: 'assistant_file',
    file_name: '已失效的临时文件.xlsx',
    file_type: 'xlsx',
    file_size: null,
    download_status: 'unavailable',
    download_url: null,
    created_at: '2026-08-12T09:21:41+08:00',
  },
  {
    id: 'mock-file-feishu',
    role: 'assistant',
    kind: 'assistant_file',
    file_name: '跨应用生成结果.xlsx',
    file_type: 'xlsx',
    file_size: 838_860,
    download_status: 'view_in_feishu',
    download_url: null,
    created_at: '2026-08-12T09:21:44+08:00',
  },
  {
    id: 'mock-unsupported',
    role: 'assistant',
    kind: 'unsupported',
    label: '暂不支持在网页中展示此类型的飞书消息，请前往原群查看。',
    created_at: '2026-08-12T09:21:50+08:00',
  },
];

const SEND_STATE_MESSAGES: ChatDisplayMessage[] = [
  ...READY_MESSAGES.slice(0, 2),
  {
    id: 'mock-user-sending',
    role: 'user',
    kind: 'user_text',
    body_text: '这条消息正在发送。',
    created_at: '2026-08-12T09:24:00+08:00',
    delivery_state: 'sending',
  },
  {
    id: 'mock-user-failed',
    role: 'user',
    kind: 'user_text',
    body_text: '这条消息用于预览发送失败和重试入口。',
    created_at: '2026-08-12T09:24:05+08:00',
    delivery_state: 'failed',
    delivery_error: '网络连接中断',
  },
];

const READY_LIST_STATE: ChatMessageListViewState = {
  status: 'ready',
  has_more: true,
  error_message: null,
};

export const CHAT_MOCK_MESSAGE_VIEWS: Record<ChatMockMessageViewKey, ChatMockMessageView> = {
  showcase: {
    key: 'showcase',
    label: '完整消息展示',
    description: 'Markdown、文件和不支持消息',
    messages: READY_MESSAGES,
    message_list: READY_LIST_STATE,
  },
  empty: {
    key: 'empty',
    label: '空会话',
    description: '智能体可用，但尚无聊天记录',
    messages: [],
    message_list: { status: 'ready', has_more: false, error_message: null },
  },
  loading: {
    key: 'loading',
    label: '首次加载',
    description: '聊天记录骨架屏',
    messages: [],
    message_list: { status: 'loading', has_more: false, error_message: null },
  },
  error: {
    key: 'error',
    label: '加载失败',
    description: '首次加载失败和重试入口',
    messages: [],
    message_list: { status: 'error', has_more: false, error_message: '暂时无法读取聊天投影，请检查网络后重试。' },
  },
  loading_more: {
    key: 'loading_more',
    label: '加载更早消息',
    description: '已有消息时加载历史分页',
    messages: READY_MESSAGES,
    message_list: { status: 'loading_more', has_more: true, error_message: null },
  },
  send_states: {
    key: 'send_states',
    label: '发送状态',
    description: '发送中、失败和重试入口',
    messages: SEND_STATE_MESSAGES,
    message_list: { status: 'ready', has_more: false, error_message: null },
  },
};

const SCENARIO_META: Record<ChatMockScenarioKey, Pick<ChatMockScenario, 'label' | 'description'>> = {
  no_agents: { label: '无可用智能体', description: '用户尚未获得任何智能体开放权限' },
  authorization_required: { label: '需要飞书授权', description: '已有平台权限，但缺少用户发送凭证' },
  not_chat_member: { label: '不是群成员', description: '平台已开放，但用户不在查宝安全群' },
  membership_unknown: { label: '成员资格未知', description: '群成员数据尚未完成首次同步' },
  membership_stale: { label: '成员快照过期', description: '成员快照超过可信时限，安全收敛' },
  backfilling: { label: '初始消息回溯', description: '正在建立最近 30 天的个人消息投影' },
  sync_delayed: { label: '消息同步延迟', description: '可读写，但新消息出现可能延迟' },
  sync_blocked: { label: '消息同步阻塞', description: '同步遇到确定性错误，禁止读写' },
  ready: { label: '正常可用', description: '可以查看消息并使用输入框' },
  maintenance: { label: '维护状态', description: '功能关闭，不读取或发送消息' },
};

function agent(status: ChatAgentAvailability): ChatAgentSummary {
  return { ...CHABAO_AGENT, status };
}

function agentStatus(overrides: Partial<ChatAgentStatus>): ChatAgentStatus {
  const defaults: ChatAgentStatus = {
    agent_key: CHABAO_AGENT.agent_key,
    platform_granted: true,
    credential_status: 'active',
    membership_status: 'active',
    sync_status: 'healthy',
    can_read: false,
    can_send: false,
    blocked_reason: null,
    last_sync_at: null,
    sync_delay_seconds: null,
  };

  return { ...defaults, ...overrides, agent_key: CHABAO_AGENT.agent_key, platform_granted: true };
}

function scenario(
  key: Exclude<ChatMockScenarioKey, 'no_agents'>,
  status: ChatAgentStatus,
  messages: ChatDisplayMessage[] = [],
): ChatMockScenario {
  return {
    key,
    ...SCENARIO_META[key],
    agents: [agent(key)],
    statuses: { [CHABAO_AGENT.agent_key]: status },
    messages,
    message_list: { status: 'ready', has_more: false, error_message: null },
  };
}

export const CHAT_MOCK_SCENARIOS: Record<ChatMockScenarioKey, ChatMockScenario> = {
  no_agents: {
    key: 'no_agents',
    ...SCENARIO_META.no_agents,
    agents: [],
    statuses: {},
    messages: [],
    message_list: { status: 'ready', has_more: false, error_message: null },
  },
  authorization_required: scenario(
    'authorization_required',
    agentStatus({
      credential_status: 'authorization_required',
      sync_status: 'disabled',
    }),
  ),
  not_chat_member: scenario(
    'not_chat_member',
    agentStatus({ membership_status: 'not_member' }),
  ),
  membership_unknown: scenario(
    'membership_unknown',
    agentStatus({
      membership_status: 'unknown',
      sync_status: 'disabled',
    }),
  ),
  membership_stale: scenario(
    'membership_stale',
    agentStatus({ membership_status: 'stale' }),
  ),
  backfilling: scenario(
    'backfilling',
    agentStatus({ sync_status: 'backfilling' }),
  ),
  sync_delayed: scenario(
    'sync_delayed',
    agentStatus({
      sync_status: 'delayed',
      can_read: true,
      can_send: true,
      last_sync_at: '2026-08-12T09:22:00+08:00',
      sync_delay_seconds: 96,
    }),
    READY_MESSAGES,
  ),
  sync_blocked: scenario(
    'sync_blocked',
    agentStatus({
      sync_status: 'blocked',
      blocked_reason: '消息同步服务不可用',
    }),
  ),
  ready: scenario(
    'ready',
    agentStatus({
      can_read: true,
      can_send: true,
      last_sync_at: '2026-08-12T09:23:36+08:00',
      sync_delay_seconds: 0,
    }),
    READY_MESSAGES,
  ),
  maintenance: scenario(
    'maintenance',
    agentStatus({ sync_status: 'disabled' }),
  ),
};

export const CHAT_MOCK_SCENARIO_OPTIONS = Object.values(CHAT_MOCK_SCENARIOS).map(
  ({ key, label, description }) => ({ key, label, description }),
);

export const CHAT_MOCK_MESSAGE_VIEW_OPTIONS = Object.values(CHAT_MOCK_MESSAGE_VIEWS).map(
  ({ key, label, description }) => ({ key, label, description }),
);

export function isChatMockScenarioKey(value: string | null): value is ChatMockScenarioKey {
  return value !== null && Object.hasOwn(CHAT_MOCK_SCENARIOS, value);
}
