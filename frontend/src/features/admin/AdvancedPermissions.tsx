import EmployeePermissionTable from './EmployeePermissionTable';
import { ADVANCED_POINTS } from './permissions';

export default function AdvancedPermissions() {
  return (
    <div className="space-y-4">
      <p className="text-xs text-zinc-500">
        高级权限决定员工能否进入后台管理的各功能：员工管理、部门管理、评分设置、企业设置。默认不开放，按需勾选。
      </p>
      <EmployeePermissionTable points={ADVANCED_POINTS} />
    </div>
  );
}
