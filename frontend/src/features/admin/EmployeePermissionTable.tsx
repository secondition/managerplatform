import { Trash2 } from 'lucide-react';
import UserProfileLink from '@/components/user/UserProfileLink';
import type { EmployeeOut } from '@/api/admin';
import type { PermissionPoint } from './permissions';
import {
  useDeleteEmployee,
  useDepartments,
  useEmployees,
  useSetEmployeePermissions,
  useSetEmployeeStatus,
} from './hooks';

// Shared employee grid. `points` selects which permission columns to render;
// toggling merges against the employee's full permission set so the columns not
// shown here (feature vs advanced) are never clobbered. `showStatusActions`
// adds the enable/disable + delete columns (employee tab only).
export default function EmployeePermissionTable({
  points,
  showStatusActions = false,
  ownerEditable = false,
}: {
  points: PermissionPoint[];
  showStatusActions?: boolean;
  // Feature columns: owner reflects real rows and can toggle their own. Advanced
  // columns keep owner locked+checked (owner bypasses admin:* by role).
  ownerEditable?: boolean;
}) {
  const employees = useEmployees();
  const departments = useDepartments();
  const setPermissions = useSetEmployeePermissions();
  const setStatus = useSetEmployeeStatus();
  const deleteEmployee = useDeleteEmployee();

  const deptName = (id: number | null) =>
    departments.data?.find((d) => d.id === id)?.name ?? '-';

  const togglePermission = (emp: EmployeeOut, point: string) => {
    if (emp.role === 'owner' && !ownerEditable) return;
    const set = new Set(emp.permissions);
    if (set.has(point)) set.delete(point);
    else set.add(point);
    setPermissions.mutate({ id: emp.id, permissions: [...set] });
  };

  return (
    <div className="bg-white rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.02)] overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr className="border-b border-zinc-100 text-[10px] uppercase tracking-wider text-zinc-400">
            <th className="text-left font-semibold px-4 py-3 min-w-[180px]">员工</th>
            <th className="font-semibold px-2 py-3">部门</th>
            {points.map((p) => (
              <th key={p.key} className="font-semibold px-2 py-3 whitespace-nowrap">{p.label}</th>
            ))}
            {showStatusActions && (
              <>
                <th className="font-semibold px-2 py-3">状态</th>
                <th className="font-semibold px-2 py-3">最近同步</th>
                <th className="font-semibold px-2 py-3">操作</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {employees.data?.map((emp) => (
            <tr key={emp.id} className="border-b border-zinc-50 hover:bg-zinc-50/30">
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <UserProfileLink user={emp} size={26} showName={false} className="shrink-0" />
                  <div>
                    <UserProfileLink
                      user={emp}
                      size={0}
                      avatarClassName="hidden"
                      nameClassName="font-semibold text-zinc-800 truncate"
                    />
                    {emp.role === 'owner' && <span className="text-[9px] text-amber-600">Owner</span>}
                    {emp.email && <div className="text-[10px] text-zinc-400">{emp.email}</div>}
                  </div>
                </div>
              </td>
              <td className="px-2 py-3 text-center text-zinc-500">{deptName(emp.department_id)}</td>
              {points.map((p) => {
                const ownerLocked = emp.role === 'owner' && !ownerEditable;
                const owned = ownerLocked || emp.permissions.includes(p.key);
                return (
                  <td key={p.key} className="px-2 py-3 text-center">
                    <input
                      type="checkbox"
                      checked={owned}
                      disabled={ownerLocked || setPermissions.isPending}
                      onChange={() => togglePermission(emp, p.key)}
                      className="w-4 h-4 rounded border-zinc-300 accent-[var(--theme-accent)] cursor-pointer disabled:cursor-not-allowed"
                    />
                  </td>
                );
              })}
              {showStatusActions && (
                <>
                  <td className="px-2 py-3 text-center">
                    {emp.role === 'owner' ? (
                      <span className="text-[10px] text-zinc-400">不可禁用</span>
                    ) : (
                      <button
                        onClick={() =>
                          setStatus.mutate({
                            id: emp.id,
                            status: emp.status === 'active' ? 'disabled' : 'active',
                          })
                        }
                        className={`px-2 py-0.5 rounded-full text-[10px] font-medium cursor-pointer ${
                          emp.status === 'active'
                            ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                            : 'bg-zinc-100 text-zinc-500 hover:bg-zinc-200'
                        }`}
                      >
                        {emp.status === 'active' ? '已启用' : '已禁用'}
                      </button>
                    )}
                  </td>
                  <td className="px-2 py-3 text-center text-[10px] text-zinc-400">
                    {emp.last_synced_at ? emp.last_synced_at.slice(0, 16).replace('T', ' ') : '-'}
                  </td>
                  <td className="px-2 py-3 text-center">
                    {emp.role === 'owner' ? (
                      <span className="text-[10px] text-zinc-300">—</span>
                    ) : (
                      <button
                        onClick={() =>
                          window.confirm(`删除员工「${emp.name}」？删除后其账号将无法登录。`) &&
                          deleteEmployee.mutate(emp.id)
                        }
                        disabled={deleteEmployee.isPending}
                        title="删除员工"
                        className="text-zinc-300 hover:text-red-600 disabled:opacity-40 p-1 rounded cursor-pointer"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
