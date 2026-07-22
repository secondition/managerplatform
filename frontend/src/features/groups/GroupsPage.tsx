import { useState } from 'react';
import { Check, Download, Pencil, Plus, Trash2, Users, UsersRound, X } from 'lucide-react';
import UserSelectPopover from '@/components/user/UserSelectPopover';
import {
  useCreateGroup,
  useCreateGroupFromDepartment,
  useDeleteGroup,
  useGroupImportSources,
  useGroups,
  useSetGroupMembers,
  useUpdateGroup,
} from './hooks';

// 人员组：全公司共享变量池。持 feature:group 的员工可编辑；组成员被日报派发、
// 红绿灯成员等选择器展开使用（选择器读取走 /users/groups，对所有员工开放）。
export default function GroupsPage() {
  const groups = useGroups();
  const importSources = useGroupImportSources();

  return (
    <div className="space-y-6 max-w-[900px] w-full mx-auto px-4 md:px-8 py-6">
      <div className="bg-white rounded-2xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.015)]">
        <div className="flex items-center gap-2">
          <span className="p-1.5 bg-[var(--theme-accent-soft)] text-[var(--theme-icon-color)] rounded-lg">
            <UsersRound size={14} />
          </span>
          <h2 className="text-base font-bold text-zinc-900">人员组</h2>
        </div>
        <p className="text-xs text-zinc-400 mt-1">
          全公司共享的人员组，可在日报派发、红绿灯成员等处快速选人。可手动建组或从部门导入成员。
        </p>
      </div>

      <GroupPanel groups={groups.data ?? []} importSources={importSources.data ?? []} />
    </div>
  );
}

function GroupPanel({
  groups,
  importSources,
}: {
  groups: import('@/api/admin').GroupOut[];
  importSources: import('@/api/groups').GroupImportSource[];
}) {
  const create = useCreateGroup();
  const update = useUpdateGroup();
  const setMembers = useSetGroupMembers();
  const fromDept = useCreateGroupFromDepartment();
  const remove = useDeleteGroup();
  const [name, setName] = useState('');
  const [importDeptId, setImportDeptId] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');

  const add = () => {
    if (!name.trim() || create.isPending) return;
    create.mutate({ name: name.trim() }, { onSuccess: () => setName('') });
  };

  const importFromDept = () => {
    if (!importDeptId || fromDept.isPending) return;
    fromDept.mutate(
      { departmentId: Number(importDeptId) },
      { onSuccess: () => setImportDeptId('') },
    );
  };

  return (
    <div className="bg-white rounded-2xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] space-y-3">
      <h3 className="text-sm font-bold text-zinc-900">人员组（{groups.length}）</h3>

      {/* 新建空组 */}
      <div className="flex items-center gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
          placeholder="新人员组名称…"
          className="flex-1 bg-zinc-50/80 rounded-lg px-3 py-2 text-xs outline-none focus:bg-zinc-100"
        />
        <button
          onClick={add}
          disabled={!name.trim() || create.isPending}
          className="flex items-center gap-1 bg-[var(--theme-accent)] hover:bg-[var(--theme-accent-hover)] disabled:opacity-40 text-white px-3 py-2 rounded-lg text-xs cursor-pointer"
        >
          <Plus size={14} />
          添加
        </button>
      </div>

      {/* 从部门导入（快照当前成员，导入后与部门解耦） */}
      <div className="flex items-center gap-2">
        <select
          value={importDeptId}
          onChange={(e) => setImportDeptId(e.target.value)}
          className="flex-1 bg-zinc-50/80 rounded-lg px-2 py-2 text-xs outline-none cursor-pointer"
        >
          <option value="">按部门导入成员…</option>
          {importSources.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
        <button
          onClick={importFromDept}
          disabled={!importDeptId || fromDept.isPending}
          className="flex items-center gap-1 bg-zinc-100 hover:bg-zinc-200 disabled:opacity-40 text-zinc-600 px-3 py-2 rounded-lg text-xs cursor-pointer"
        >
          <Download size={14} />
          导入
        </button>
      </div>

      <div className="space-y-1">
        {groups.map((g) => (
          <GroupRow
            key={g.id}
            group={g}
            editing={editingId === g.id}
            editName={editName}
            onEditName={setEditName}
            onStartEdit={() => {
              setEditName(g.name);
              setEditingId(g.id);
            }}
            onCancelEdit={() => setEditingId(null)}
            onSaveEdit={() =>
              update.mutate(
                { id: g.id, input: { name: editName.trim() } },
                { onSuccess: () => setEditingId(null) },
              )
            }
            onSetMembers={(ids) => setMembers.mutate({ id: g.id, memberIds: ids })}
            onRemove={() => window.confirm(`删除人员组「${g.name}」？`) && remove.mutate(g.id)}
          />
        ))}
        {groups.length === 0 && (
          <p className="text-center text-xs text-zinc-400 py-4">还没有人员组。</p>
        )}
      </div>
    </div>
  );
}

function GroupRow({
  group: g,
  editing,
  editName,
  onEditName,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onSetMembers,
  onRemove,
}: {
  group: import('@/api/admin').GroupOut;
  editing: boolean;
  editName: string;
  onEditName: (v: string) => void;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onSaveEdit: () => void;
  onSetMembers: (ids: number[]) => void;
  onRemove: () => void;
}) {
  return (
    <div className="group flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-zinc-50/70">
      {editing ? (
        <>
          <input
            value={editName}
            onChange={(e) => onEditName(e.target.value)}
            className="flex-1 bg-white border border-[var(--theme-accent)] rounded px-2 py-1 text-xs outline-none"
          />
          <button onClick={onSaveEdit} className="text-[var(--theme-accent)] cursor-pointer">
            <Check size={14} />
          </button>
          <button onClick={onCancelEdit} className="text-zinc-400 cursor-pointer">
            <X size={14} />
          </button>
        </>
      ) : (
        <>
          <span className="flex-1 text-xs text-zinc-700 flex items-center gap-1.5">
            {g.name}
            <span className="inline-flex items-center gap-0.5 text-[10px] text-zinc-400">
              <Users size={11} />
              {g.member_ids.length}
            </span>
            {g.source === 'department' && (
              <span className="text-[10px] text-blue-400">来自部门</span>
            )}
          </span>
          <UserSelectPopover
            label="成员"
            multiple
            selectedIds={g.member_ids}
            onChange={onSetMembers}
            triggerClassName="opacity-0 group-hover:opacity-100"
          />
          <button
            onClick={onStartEdit}
            className="text-zinc-300 hover:text-[var(--theme-accent)] opacity-0 group-hover:opacity-100 p-1 cursor-pointer"
          >
            <Pencil size={12} />
          </button>
          <button
            onClick={onRemove}
            className="text-zinc-300 hover:text-red-600 opacity-0 group-hover:opacity-100 p-1 cursor-pointer"
          >
            <Trash2 size={12} />
          </button>
        </>
      )}
    </div>
  );
}
