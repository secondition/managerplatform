import { useState } from 'react';
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react';
import type { DepartmentOut } from '@/api/admin';
import {
  useCreateDepartment,
  useDeleteDepartment,
  useDepartments,
  useUpdateDepartment,
} from './hooks';

// 人员组管理已迁至独立页面 features/groups；此组件仅保留部门管理。
export default function OrgManage({ show }: { show: 'department' }) {
  void show;
  const departments = useDepartments();
  return (
    <div className="max-w-2xl">
      <DepartmentPanel departments={departments.data ?? []} />
    </div>
  );
}

function DepartmentPanel({ departments }: { departments: DepartmentOut[] }) {
  const create = useCreateDepartment();
  const update = useUpdateDepartment();
  const remove = useDeleteDepartment();
  const [name, setName] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');

  const add = () => {
    if (!name.trim() || create.isPending) return;
    create.mutate({ name: name.trim() }, { onSuccess: () => setName('') });
  };

  return (
    <div className="bg-white rounded-2xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] space-y-3">
      <h3 className="text-sm font-bold text-zinc-900">部门（{departments.length}）</h3>
      <div className="flex items-center gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
          placeholder="新部门名称…"
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
      <div className="space-y-1">
        {departments.map((d) => (
          <div key={d.id} className="group flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-zinc-50/70">
            {editingId === d.id ? (
              <>
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="flex-1 bg-white border border-[var(--theme-accent)] rounded px-2 py-1 text-xs outline-none"
                />
                <button
                  onClick={() => {
                    update.mutate({ id: d.id, input: { name: editName.trim() } }, { onSuccess: () => setEditingId(null) });
                  }}
                  className="text-[var(--theme-accent)] cursor-pointer"
                >
                  <Check size={14} />
                </button>
                <button onClick={() => setEditingId(null)} className="text-zinc-400 cursor-pointer">
                  <X size={14} />
                </button>
              </>
            ) : (
              <>
                <span className="flex-1 text-xs text-zinc-700">{d.name}</span>
                <button
                  onClick={() => {
                    setEditName(d.name);
                    setEditingId(d.id);
                  }}
                  className="text-zinc-300 hover:text-[var(--theme-accent)] opacity-0 group-hover:opacity-100 p-1 cursor-pointer"
                >
                  <Pencil size={12} />
                </button>
                <button
                  onClick={() => window.confirm(`删除部门「${d.name}」？`) && remove.mutate(d.id)}
                  className="text-zinc-300 hover:text-red-600 opacity-0 group-hover:opacity-100 p-1 cursor-pointer"
                >
                  <Trash2 size={12} />
                </button>
              </>
            )}
          </div>
        ))}
        {departments.length === 0 && (
          <p className="text-center text-xs text-zinc-400 py-4">还没有部门。</p>
        )}
      </div>
    </div>
  );
}
