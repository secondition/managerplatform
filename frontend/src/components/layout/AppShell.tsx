import type { ReactNode } from 'react';
import { ChevronLeft, LogOut, Settings } from 'lucide-react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { logout as apiLogout } from '@/api/auth';
import Avatar from '@/components/user/Avatar';
import ThemePicker from '@/components/layout/ThemePicker';
import { usePublicSettings } from '@/features/settings/hooks';
import { useAuthStore } from '@/stores/authStore';
import AvatarPhysicsField from '@/features/playground/AvatarPhysicsField';
import NotificationCenter from '@/features/notifications/NotificationCenter';

type NavItem = {
  to: string;
  label: string;
  permission?: string | null;
  ownerOnly?: boolean;
  disabled?: boolean;
  disabledHint?: string;
};

const NAV: NavItem[] = [
  { to: '/daily', label: '日报', permission: 'feature:daily' },
  { to: '/chat', label: 'AI 大脑' },
  { to: '/traffic-light', label: '红绿灯', permission: 'feature:traffic' },
  { to: '/okr', label: 'OKR', permission: 'feature:okr' },
  { to: '/subscription/daily', label: '订阅·日报', permission: 'feature:daily' },
  { to: '/subscription/okr', label: '订阅·OKR', permission: 'feature:okr' },
  { to: '/groups', label: '人员组', permission: 'feature:group' },
  { to: '/inspirations', label: '灵感库', disabled: true, disabledHint: '功能预留，暂未开放' },
  { to: '/documents', label: '文档', disabled: true, disabledHint: '功能预留，暂未开放' },
  { to: '/knowledge', label: '知识库', disabled: true, disabledHint: '功能预留，暂未开放' },
  { to: '/data-tables', label: '多维表格', disabled: true, disabledHint: '功能预留，暂未开放' },
];

const ADMIN_NAV: NavItem[] = [
  { to: '/admin/notification-settings', label: '通知设置', permission: 'admin:notification' },
  { to: '/admin/employees', label: '人员管理', permission: 'admin:employee' },
  { to: '/admin/sync-history', label: '同步记录', permission: 'admin:employee' },
  { to: '/admin/permissions', label: '权限管理', ownerOnly: true },
  { to: '/admin/departments', label: '部门管理', permission: 'admin:department' },
  { to: '/admin/scoring-settings', label: '评分设置', permission: 'admin:ai' },
  {
    to: '/admin/agent-settings',
    label: '智能体设置',
    permission: 'admin:agent',
  },
  { to: '/admin/company-settings', label: '企业设置', permission: 'admin:settings' },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const clearSession = useAuthStore((state) => state.clearSession);
  const navigate = useNavigate();
  const location = useLocation();
  const companySettings = usePublicSettings();
  const companyName = companySettings.data?.company_name ?? '管理工作台';
  const logoUrl = companySettings.data?.logo_url;
  const footerText = companySettings.data?.footer_text;
  const isAdmin = location.pathname === '/admin' || location.pathname.startsWith('/admin/');
  const canAdmin =
    hasPermission('admin:employee') ||
    hasPermission('admin:department') ||
    hasPermission('admin:ai') ||
    hasPermission('admin:agent') ||
    hasPermission('admin:settings') ||
    hasPermission('admin:notification');

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch {
      // Local session is still cleared when the remote session has expired.
    }
    clearSession();
    navigate('/login', { replace: true });
  };

  const navItems = (isAdmin ? ADMIN_NAV : NAV).filter((item) => {
    if (item.ownerOnly && user?.role !== 'owner') return false;
    if (item.disabled) return true;
    if (!item.permission) return true;
    return hasPermission(item.permission);
  });

  return (
    <div className="min-h-screen bg-[#f8f9fa] text-[#111827]">
      <header className="sticky top-0 z-40 h-[var(--app-header-height)] border-b border-[#e6eaf1] bg-white/95 backdrop-blur-md">
        <div className={`mx-auto flex h-12 items-center justify-between px-4 sm:px-7 ${isAdmin ? 'max-w-[1312px]' : 'max-w-[1392px]'}`}>
          {isAdmin ? (
            <div className="flex items-center gap-3">
              {logoUrl ? (
                <img src={logoUrl} alt={companyName} className="h-7 w-7 rounded-lg object-cover" />
              ) : (
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-xs font-bold text-white shadow-sm">W</span>
              )}
              <button
                onClick={() => navigate('/daily')}
                className="flex items-center gap-1 rounded-lg border border-[var(--theme-accent)] bg-[var(--theme-accent-soft)] px-2.5 py-1 text-xs font-medium text-[var(--theme-accent)] hover:bg-white"
              >
                <ChevronLeft size={13} /> 返回工作台
              </button>
              <span className="text-sm font-semibold text-[#111827]">管理后台</span>
            </div>
          ) : (
            <NavLink to="/daily" className="flex items-center gap-2">
              {logoUrl ? (
                <img src={logoUrl} alt={companyName} className="h-7 w-7 rounded-lg object-cover" />
              ) : (
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-xs font-bold text-white shadow-sm">W</span>
              )}
              <span className="text-sm font-semibold text-[#111827]">{companyName}</span>
            </NavLink>
          )}

          <div className="flex items-center gap-3 text-xs text-slate-500">
            <ThemePicker />
            {!isAdmin && (
              <>
                <NotificationCenter />
                {canAdmin && (
                  <NavLink to="/admin" className="flex items-center gap-1 text-[var(--theme-accent)] hover:opacity-80" title="管理后台">
                    <Settings size={13} />
                    <span>管理后台</span>
                  </NavLink>
                )}
              </>
            )}
            <NavLink to="/people/me" className="flex items-center gap-1.5 font-medium text-slate-700 hover:text-[var(--theme-accent)]">
              {isAdmin && user && <Avatar name={user.name} avatarUrl={user.avatar_url} size={18} />}
              <span className="max-w-[112px] truncate">{user?.name ?? '故障机器人'}</span>
            </NavLink>
            <button onClick={handleLogout} className="rounded p-1 text-slate-400 hover:bg-slate-50 hover:text-slate-700" title="退出登录">
              <LogOut size={15} />
            </button>
          </div>
        </div>

        <nav className="mx-auto flex h-12 max-w-[1362px] items-end gap-1 overflow-x-auto px-4 sm:px-7">
          {navItems.map((item) =>
            item.disabled ? (
              <span
                key={item.to}
                title={item.disabledHint ?? '功能预留，暂未开放'}
                className="relative flex h-12 shrink-0 cursor-not-allowed items-center px-3 text-[13px] text-slate-300"
              >
                {item.label}
              </span>
            ) : (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `relative flex h-12 shrink-0 items-center px-3 text-[13px] transition-colors after:absolute after:inset-x-2 after:bottom-1 after:h-0.5 after:rounded-full ${
                    isActive
                      ? 'font-semibold text-[var(--theme-accent)] after:bg-[var(--theme-accent)]'
                      : 'text-slate-600 after:bg-transparent hover:text-slate-900'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ),
          )}
        </nav>
      </header>

      <main className={`min-h-[calc(100vh-var(--app-header-height))] ${isAdmin ? 'bg-[#f5f8fc]' : ''}`}>
        {children}
      </main>
      {footerText && <footer className="py-6 text-center text-[10px] text-slate-400">{footerText}</footer>}
      <AvatarPhysicsField />
    </div>
  );
}
