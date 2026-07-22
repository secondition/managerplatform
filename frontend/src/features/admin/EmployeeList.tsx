import { RefreshCw } from 'lucide-react';
import EmployeePermissionTable from './EmployeePermissionTable';
import { FEATURE_POINTS } from './permissions';
import { useSyncFeishuContacts } from './hooks';

export default function EmployeeList() {
  const syncContacts = useSyncFeishuContacts();

  return (
    <div className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <p className="text-xs text-zinc-500">
            员工来自飞书通讯录同步。此处配置每位员工可使用的功能，未勾选则其导航栏不显示对应入口。
          </p>
          {syncContacts.data && (
            <p className="mt-1 text-[11px] text-emerald-700">
              同步完成：新增 {syncContacts.data.created}，更新 {syncContacts.data.updated}，禁用 {syncContacts.data.disabled}，跳过 {syncContacts.data.skipped}。
            </p>
          )}
          {syncContacts.isError && (
            <p className="mt-1 text-[11px] text-red-600">同步失败，请检查飞书应用权限与后端配置。</p>
          )}
        </div>
        <button
          onClick={() => syncContacts.mutate()}
          disabled={syncContacts.isPending}
          className="flex items-center gap-1 bg-[var(--theme-accent)] hover:bg-[var(--theme-accent-hover)] disabled:opacity-50 text-white rounded-xl px-4 py-2 text-xs font-semibold cursor-pointer shrink-0"
        >
          <RefreshCw size={14} className={syncContacts.isPending ? 'animate-spin' : ''} />
          {syncContacts.isPending ? '同步中…' : '从飞书同步通讯录'}
        </button>
      </div>

      <EmployeePermissionTable points={FEATURE_POINTS} showStatusActions ownerEditable />
    </div>
  );
}
