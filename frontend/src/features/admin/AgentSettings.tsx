import {
  Bot,
  CircleAlert,
  ImageUp,
  LoaderCircle,
  RotateCcw,
  Save,
  Settings2,
  ShieldCheck,
  Trash2,
  UserPlus,
  UsersRound,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import GroupSelectPopover, {
  type GroupSelectItem,
} from '@/components/user/GroupSelectPopover';
import UserSelectPopover from '@/components/user/UserSelectPopover';
import Avatar from '@/components/user/Avatar';
import type { AdminAgentOut } from '@/api/admin';
import type { UserBrief } from '@/types/api';
import {
  useAdminAgents,
  useAgentAccess,
  useAgentFeishuChatConfig,
  useRemoveAgentAvatar,
  useReplaceAgentAccess,
  useUpdateAgentFeishuChatConfig,
  useUpdateAgentPresentation,
  useUploadAgentAvatar,
} from './hooks';

export default function AgentSettings() {
  const agentsQuery = useAdminAgents();
  const agents = agentsQuery.data ?? [];
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);

  useEffect(() => {
    if (selectedAgentId !== null || agents.length === 0) return;
    setSelectedAgentId(agents[0].id);
  }, [agents, selectedAgentId]);

  if (agentsQuery.isPending) return <AgentSettingsLoading />;
  if (agentsQuery.isError) {
    return <AgentSettingsFailure onRetry={() => void agentsQuery.refetch()} />;
  }
  if (agents.length === 0) {
    return (
      <section className="workspace-card px-6 py-10 text-center text-xs text-slate-500">
        当前没有可配置的智能体。
      </section>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
      <section className="workspace-card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">智能体</h2>
          <p className="mt-1 text-[11px] text-slate-400">选择需要配置开放范围的智能体</p>
        </div>
        <div className="space-y-1.5 p-2.5">
          {agents.map((agent) => (
            <button
              key={agent.id}
              type="button"
              onClick={() => setSelectedAgentId(agent.id)}
              className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors ${
                selectedAgentId === agent.id
                  ? 'bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]'
                  : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <AgentIcon agent={agent} />
              <span className="min-w-0 flex-1">
                <strong className="block truncate text-xs font-semibold">{agent.name}</strong>
                <span className="mt-0.5 block text-[10px] opacity-70">
                  {agent.effective_user_count} 名授权用户 · {agent.group_count} 个人员组
                </span>
              </span>
            </button>
          ))}
        </div>
      </section>

      {selectedAgentId !== null ? (
        <AgentAccessPanel key={selectedAgentId} agentId={selectedAgentId} />
      ) : null}
    </div>
  );
}

function AgentAccessPanel({ agentId }: { agentId: number }) {
  const accessQuery = useAgentAccess(agentId);
  const replaceAccess = useReplaceAgentAccess();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<UserBrief[]>([]);
  const [selectedGroupIds, setSelectedGroupIds] = useState<number[]>([]);
  const [selectedGroups, setSelectedGroups] = useState<GroupSelectItem[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!accessQuery.data || dirty) return;
    setSelectedIds(accessQuery.data.users.map((user) => user.id));
    setSelectedUsers(accessQuery.data.users.map((user) => ({
      id: user.id,
      name: user.name,
      avatar_url: user.avatar_url,
      department_id: null,
    })));
    setSelectedGroupIds(accessQuery.data.groups.map((group) => group.id));
    setSelectedGroups(accessQuery.data.groups.map((group) => ({
      id: group.id,
      name: group.name,
      memberCount: group.member_count,
    })));
  }, [accessQuery.data, dirty]);

  const selectedUserMap = useMemo(
    () => new Map(selectedUsers.map((user) => [user.id, user])),
    [selectedUsers],
  );
  const selectedGroupMap = useMemo(
    () => new Map(selectedGroups.map((group) => [group.id, group])),
    [selectedGroups],
  );

  if (accessQuery.isPending) return <AgentSettingsLoading />;
  if (accessQuery.isError || !accessQuery.data) {
    return <AgentSettingsFailure onRetry={() => void accessQuery.refetch()} />;
  }

  const access = accessQuery.data;

  function handleUserSelection(nextIds: number[], users: UserBrief[] = []) {
    const knownUsers = new Map(selectedUserMap);
    users.forEach((user) => knownUsers.set(user.id, user));
    setSelectedIds(nextIds);
    setSelectedUsers(nextIds.flatMap((id) => {
      const user = knownUsers.get(id);
      return user ? [user] : [];
    }));
    setDirty(true);
    setNotice(null);
  }

  function handleGroupSelection(nextIds: number[], groups: GroupSelectItem[]) {
    setSelectedGroupIds(nextIds);
    setSelectedGroups(groups);
    setDirty(true);
    setNotice(null);
  }

  function save() {
    if (replaceAccess.isPending) return;
    replaceAccess.mutate(
      { agentId, userIds: selectedIds, groupIds: selectedGroupIds },
      {
        onSuccess: (data) => {
          setDirty(false);
          setNotice(`已保存 ${data.users.length} 名直接用户和 ${data.groups.length} 个人员组，并已触发即时群成员校验。`);
        },
        onError: () => setNotice('授权范围保存失败，请稍后重试。'),
      },
    );
  }

  function clearAccess() {
    if (replaceAccess.isPending) return;
    if (!window.confirm(`确认撤销“${access.agent.name}”的全部直接用户和人员组授权？`)) return;
    replaceAccess.mutate(
      { agentId, userIds: [], groupIds: [] },
      {
        onSuccess: () => {
          setSelectedIds([]);
          setSelectedUsers([]);
          setSelectedGroupIds([]);
          setSelectedGroups([]);
          setDirty(false);
          setNotice('已撤销全部智能体授权。');
        },
        onError: () => setNotice('撤销失败，请稍后重试。'),
      },
    );
  }

  return (
    <section className="workspace-card min-w-0 overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-900">{access.agent.name}授权范围</h2>
            <span className={`rounded-full px-2 py-0.5 text-[10px] ${
              access.agent.enabled
                ? 'bg-emerald-50 text-emerald-600'
                : 'bg-slate-100 text-slate-500'
            }`}>
              {access.agent.enabled ? '智能体已启用' : '智能体已停用'}
            </span>
          </div>
          <p className="mt-1 text-[11px] leading-5 text-slate-500">{access.agent.description}</p>
        </div>
        <div className="flex flex-wrap justify-end gap-2 text-center text-[10px]">
          <CountCard label="直接用户" value={access.agent.direct_user_count} />
          <CountCard label="人员组" value={access.agent.group_count} />
          <CountCard label="授权用户" value={access.agent.effective_user_count} />
          <CountCard label="群内用户" value={access.agent.chat_member_count} />
          <CountCard label="非群成员" value={access.agent.non_chat_member_count} warning />
        </div>
      </div>

      <div className="space-y-4 p-5">
        <AgentPresentationEditor agent={access.agent} />
        <AgentFeishuChatConfigEditor agentId={access.agent.id} />

        <div className="rounded-xl border border-blue-100 bg-blue-50/70 p-3 text-[11px] leading-5 text-blue-700">
          <strong className="flex items-center gap-1.5 font-semibold">
            <ShieldCheck size={13} /> 智能体访问条件
          </strong>
          <p className="mt-1">
            员工获得直接授权或人员组授权后，还需要具备目标飞书群成员资格，才能在 AI 大脑中使用该智能体。
          </p>
        </div>

        <div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-slate-800">直接授权用户</h3>
              <p className="mt-1 text-[10px] text-slate-400">当前选择 {selectedIds.length} 人</p>
            </div>
            <UserSelectPopover
              selectedIds={selectedIds}
              selectedUsers={selectedUsers}
              onChange={handleUserSelection}
              label="选择员工"
              icon={<UserPlus size={12} />}
              multiple
              includeGroups={false}
            />
          </div>

          <div className="mt-3 min-h-24 rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-3">
            {selectedIds.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {selectedIds.map((userId) => {
                  const user = selectedUserMap.get(userId);
                  if (!user) return null;
                  return (
                    <span key={user.id} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white py-1 pl-1 pr-2 text-[11px] text-slate-600">
                      <Avatar name={user.name} avatarUrl={user.avatar_url} size={22} />
                      <span>{user.name}</span>
                      <button
                        type="button"
                        onClick={() => handleUserSelection(
                          selectedIds.filter((id) => id !== user.id),
                          selectedUsers.filter((item) => item.id !== user.id),
                        )}
                        className="text-slate-300 hover:text-rose-500"
                        aria-label={`移除${user.name}`}
                      >
                        <X size={11} />
                      </button>
                    </span>
                  );
                })}
              </div>
            ) : (
              <div className="flex min-h-16 items-center justify-center text-[11px] text-slate-400">
                尚未选择直接授权用户
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-slate-800">授权人员组</h3>
              <p className="mt-1 text-[10px] text-slate-400">当前选择 {selectedGroupIds.length} 个组</p>
            </div>
            <GroupSelectPopover
              selectedIds={selectedGroupIds}
              selectedGroups={selectedGroups}
              onChange={handleGroupSelection}
              label="选择人员组"
              icon={<UsersRound size={12} />}
            />
          </div>

          <div className="mt-3 min-h-24 rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-3">
            {selectedGroupIds.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {selectedGroupIds.map((groupId) => {
                  const group = selectedGroupMap.get(groupId);
                  if (!group) return null;
                  return (
                    <span key={group.id} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white py-1 pl-2 pr-2 text-[11px] text-slate-600">
                      <UsersRound size={12} className="text-[var(--theme-accent)]" />
                      <span>{group.name}</span>
                      <span className="text-[10px] text-slate-400">{group.memberCount} 人</span>
                      <button
                        type="button"
                        onClick={() => handleGroupSelection(
                          selectedGroupIds.filter((id) => id !== group.id),
                          selectedGroups.filter((item) => item.id !== group.id),
                        )}
                        className="text-slate-300 hover:text-rose-500"
                        aria-label={`移除${group.name}`}
                      >
                        <X size={11} />
                      </button>
                    </span>
                  );
                })}
              </div>
            ) : (
              <div className="flex min-h-16 items-center justify-center text-[11px] text-slate-400">
                尚未选择授权人员组
              </div>
            )}
          </div>
        </div>

        {notice ? (
          <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-600" role="status">
            {notice}
          </p>
        ) : null}

        <div className="flex flex-wrap justify-between gap-2 border-t border-slate-100 pt-4">
          <button type="button" className="workspace-button text-rose-600" onClick={clearAccess} disabled={replaceAccess.isPending}>
            <RotateCcw size={12} /> 撤销全部授权
          </button>
          <button
            type="button"
            className="workspace-button workspace-button-primary"
            onClick={save}
            disabled={!dirty || replaceAccess.isPending}
          >
            {replaceAccess.isPending ? <LoaderCircle size={12} className="animate-spin" /> : <Save size={12} />}
            保存授权范围
          </button>
        </div>
      </div>
    </section>
  );
}

function AgentPresentationEditor({ agent }: { agent: AdminAgentOut }) {
  const updatePresentation = useUpdateAgentPresentation();
  const uploadAvatar = useUploadAgentAvatar();
  const removeAvatar = useRemoveAgentAvatar();
  const [name, setName] = useState(agent.name);
  const [description, setDescription] = useState(agent.description);
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const presentationPending = updatePresentation.isPending
    || uploadAvatar.isPending
    || removeAvatar.isPending;

  useEffect(() => {
    if (dirty) return;
    setName(agent.name);
    setDescription(agent.description);
  }, [agent.name, agent.description, dirty]);

  function savePresentation() {
    const normalizedName = name.trim();
    if (!normalizedName || presentationPending) return;
    updatePresentation.mutate(
      {
        agentId: agent.id,
        input: {
          name: normalizedName,
          description: description.trim(),
        },
      },
      {
        onSuccess: (data) => {
          setName(data.name);
          setDescription(data.description);
          setDirty(false);
          setNotice('智能体展示信息已保存，AI 大脑将同步显示。');
        },
        onError: () => setNotice('智能体展示信息保存失败，请稍后重试。'),
      },
    );
  }

  function handleAvatarFile(file: File) {
    if (file.size > 2 * 1024 * 1024) {
      setNotice('智能体图标不能超过 2MB。');
      return;
    }
    uploadAvatar.mutate(
      { agentId: agent.id, file },
      {
        onSuccess: () => setNotice('智能体图标已更新，AI 大脑将同步显示。'),
        onError: () => setNotice('智能体图标上传失败，请确认图片格式和大小。'),
      },
    );
  }

  function clearAvatar() {
    if (presentationPending || !agent.avatar_url) return;
    if (!window.confirm('确认恢复该智能体的默认图标？')) return;
    removeAvatar.mutate(agent.id, {
      onSuccess: () => setNotice('已恢复智能体默认图标。'),
      onError: () => setNotice('恢复默认图标失败，请稍后重试。'),
    });
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/45 p-4">
      <div>
        <h3 className="text-xs font-semibold text-slate-800">AI 大脑展示信息</h3>
        <p className="mt-1 text-[10px] text-slate-400">名称、描述和图标会展示在 AI 大脑的智能体列表与对话区域。</p>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-[150px_minmax(0,1fr)]">
        <div>
          <span className="text-[11px] font-medium text-slate-600">智能体图标</span>
          <div className="mt-2 flex h-24 w-full items-center justify-center rounded-xl border border-dashed border-slate-200 bg-white">
            {agent.avatar_url ? (
              <img src={agent.avatar_url} alt={agent.name} className="h-16 w-16 rounded-2xl object-cover shadow-sm" />
            ) : (
              <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]">
                <Bot size={26} />
              </span>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <label className={`workspace-button ${presentationPending ? 'pointer-events-none opacity-50' : 'cursor-pointer'}`}>
              {uploadAvatar.isPending ? <LoaderCircle size={12} className="animate-spin" /> : <ImageUp size={12} />}
              更换图标
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                disabled={presentationPending}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) handleAvatarFile(file);
                  event.currentTarget.value = '';
                }}
              />
            </label>
            {agent.avatar_url ? (
              <button
                type="button"
                className="workspace-button text-rose-600"
                onClick={clearAvatar}
                disabled={presentationPending}
              >
                <Trash2 size={12} /> 恢复默认
              </button>
            ) : null}
          </div>
          <p className="mt-2 text-[10px] leading-4 text-slate-400">PNG、JPG 或 WEBP，最大 2MB。</p>
        </div>

        <div className="space-y-3">
          <label className="block">
            <span className="text-[11px] font-medium text-slate-600">显示名称</span>
            <input
              value={name}
              maxLength={100}
              onChange={(event) => {
                setName(event.target.value);
                setDirty(true);
                setNotice(null);
              }}
              className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 outline-none focus:border-[var(--theme-accent)]"
              placeholder="请输入智能体名称"
            />
          </label>
          <label className="block">
            <span className="flex items-center justify-between text-[11px] font-medium text-slate-600">
              <span>显示描述</span>
              <span className="font-normal text-slate-400">{description.length}/1000</span>
            </span>
            <textarea
              value={description}
              maxLength={1000}
              rows={3}
              onChange={(event) => {
                setDescription(event.target.value);
                setDirty(true);
                setNotice(null);
              }}
              className="mt-1.5 w-full resize-y rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-800 outline-none focus:border-[var(--theme-accent)]"
              placeholder="请输入智能体能力说明"
            />
          </label>
          <button
            type="button"
            className="workspace-button workspace-button-primary"
            onClick={savePresentation}
            disabled={!dirty || !name.trim() || presentationPending}
          >
            {updatePresentation.isPending ? <LoaderCircle size={12} className="animate-spin" /> : <Save size={12} />}
            保存展示信息
          </button>
        </div>
      </div>

      {notice ? (
        <p className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-600" role="status">
          {notice}
        </p>
      ) : null}
    </div>
  );
}

function AgentFeishuChatConfigEditor({ agentId }: { agentId: number }) {
  const configQuery = useAgentFeishuChatConfig(agentId);
  const updateConfig = useUpdateAgentFeishuChatConfig();
  const [targetChatId, setTargetChatId] = useState('');
  const [targetChatName, setTargetChatName] = useState('');
  const [agentSenderId, setAgentSenderId] = useState('');
  const [agentMentionId, setAgentMentionId] = useState('');
  const [agentDisplayName, setAgentDisplayName] = useState('');
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!configQuery.data || dirty) return;
    setTargetChatId(configQuery.data.target_chat_id);
    setTargetChatName(configQuery.data.target_chat_name);
    setAgentSenderId(configQuery.data.agent_sender_id);
    setAgentMentionId(configQuery.data.agent_mention_id);
    setAgentDisplayName(configQuery.data.agent_display_name);
  }, [configQuery.data, dirty]);

  const values = [
    targetChatId,
    targetChatName,
    agentSenderId,
    agentMentionId,
    agentDisplayName,
  ];
  const complete = values.every((value) => value.trim());

  function change(setter: (value: string) => void, value: string) {
    setter(value);
    setDirty(true);
    setNotice(null);
  }

  function saveConfig() {
    if (!complete || updateConfig.isPending) return;
    updateConfig.mutate(
      {
        agentId,
        input: {
          target_chat_id: targetChatId.trim(),
          target_chat_name: targetChatName.trim(),
          agent_sender_id: agentSenderId.trim(),
          agent_mention_id: agentMentionId.trim(),
          agent_display_name: agentDisplayName.trim(),
        },
      },
      {
        onSuccess: (data) => {
          setTargetChatId(data.target_chat_id);
          setTargetChatName(data.target_chat_name);
          setAgentSenderId(data.agent_sender_id);
          setAgentMentionId(data.agent_mention_id);
          setAgentDisplayName(data.agent_display_name);
          setDirty(false);
          setNotice('飞书群连接配置已保存，后续运行将使用当前智能体配置。');
        },
        onError: () => setNotice('飞书群连接配置保存失败，请稍后重试。'),
      },
    );
  }

  if (configQuery.isPending) {
    return (
      <div className="flex min-h-28 items-center justify-center rounded-xl border border-slate-200 bg-slate-50/45 text-[11px] text-slate-500">
        <LoaderCircle size={13} className="mr-2 animate-spin" /> 正在加载飞书群连接配置…
      </div>
    );
  }
  if (configQuery.isError) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-[11px] text-rose-600" role="alert">
        飞书群连接配置加载失败，请刷新页面后重试。
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/45 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-1.5 text-xs font-semibold text-slate-800">
            <Settings2 size={13} /> 飞书群连接配置
          </h3>
          <p className="mt-1 text-[10px] leading-4 text-slate-400">
            配置当前智能体连接的目标群和机器人身份，保存后不再依赖本地环境变量。
          </p>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-[10px] ${
          configQuery.data?.complete
            ? 'bg-emerald-50 text-emerald-600'
            : 'bg-amber-50 text-amber-600'
        }`}>
          {configQuery.data?.complete ? '配置完整' : '待完善'}
        </span>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <ConfigField
          label="目标群 Chat ID"
          value={targetChatId}
          onChange={(value) => change(setTargetChatId, value)}
          placeholder="例如：oc_xxxxxxxxxxxxxxxx"
          help="飞书目标群的唯一 Chat ID。"
        />
        <ConfigField
          label="目标群名称"
          value={targetChatName}
          onChange={(value) => change(setTargetChatName, value)}
          placeholder="例如：茶包问问群"
          help="必须与飞书中的实际群名称完全一致。"
        />
        <ConfigField
          label="机器人消息发送者 ID"
          value={agentSenderId}
          onChange={(value) => change(setAgentSenderId, value)}
          placeholder="机器人回复消息中的 sender_id"
          help="用于识别哪些群消息是智能体回复。"
        />
        <ConfigField
          label="机器人 @ 提及 ID"
          value={agentMentionId}
          onChange={(value) => change(setAgentMentionId, value)}
          placeholder="用户消息 mentions 中的机器人 ID"
          help="用于识别用户是否在群中 @ 了当前智能体。"
        />
        <ConfigField
          label="机器人 @ 显示名称"
          value={agentDisplayName}
          onChange={(value) => change(setAgentDisplayName, value)}
          placeholder="例如：心选茶包（查宝）"
          help="从网页发送消息到飞书群时使用的 @ 名称。"
          className="md:col-span-2"
          maxLength={100}
        />
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 pt-4">
        <p className="text-[10px] leading-4 text-slate-400">修改目标群后，系统会为新群重新同步成员和历史消息。</p>
        <button
          type="button"
          className="workspace-button workspace-button-primary"
          onClick={saveConfig}
          disabled={!dirty || !complete || updateConfig.isPending}
        >
          {updateConfig.isPending ? <LoaderCircle size={12} className="animate-spin" /> : <Save size={12} />}
          保存飞书群配置
        </button>
      </div>

      {notice ? (
        <p className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-600" role="status">
          {notice}
        </p>
      ) : null}
    </div>
  );
}

function ConfigField({
  label,
  value,
  onChange,
  placeholder,
  help,
  className = '',
  maxLength = 200,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  help: string;
  className?: string;
  maxLength?: number;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="text-[11px] font-medium text-slate-600">{label}</span>
      <input
        value={value}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 outline-none focus:border-[var(--theme-accent)]"
        placeholder={placeholder}
      />
      <span className="mt-1 block text-[10px] leading-4 text-slate-400">{help}</span>
    </label>
  );
}

function AgentIcon({ agent }: { agent: Pick<AdminAgentOut, 'name' | 'avatar_url'> }) {
  if (agent.avatar_url) {
    return <img src={agent.avatar_url} alt="" className="h-9 w-9 shrink-0 rounded-xl object-cover shadow-sm" />;
  }
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white shadow-sm">
      <Bot size={16} />
    </span>
  );
}

function CountCard({ label, value, warning = false }: { label: string; value: number; warning?: boolean }) {
  return (
    <span className={`min-w-16 rounded-lg px-2.5 py-1.5 ${warning && value > 0 ? 'bg-amber-50 text-amber-600' : 'bg-slate-50 text-slate-500'}`}>
      <strong className="block text-xs font-semibold">{value}</strong>
      {label}
    </span>
  );
}

function AgentSettingsLoading() {
  return (
    <section className="workspace-card flex min-h-72 items-center justify-center text-xs text-slate-500" aria-busy="true">
      <LoaderCircle size={14} className="mr-2 animate-spin" /> 正在加载智能体设置…
    </section>
  );
}

function AgentSettingsFailure({ onRetry }: { onRetry: () => void }) {
  return (
    <section className="workspace-card flex min-h-72 flex-col items-center justify-center px-5 text-center" role="alert">
      <CircleAlert size={22} className="text-rose-500" />
      <strong className="mt-3 text-sm text-slate-700">智能体设置加载失败</strong>
      <button type="button" className="workspace-button mt-4" onClick={onRetry}>
        <RotateCcw size={12} /> 重试
      </button>
    </section>
  );
}
