import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import AppShell from '@/components/layout/AppShell';
import Spinner from '@/components/ui/Spinner';
import LoginPage from '@/features/auth/LoginPage';
import CallbackPage from '@/features/auth/CallbackPage';
import ChatOAuthCallbackPage from '@/features/chat/ChatOAuthCallbackPage';
import ForbiddenPage from '@/components/layout/ForbiddenPage';

const DailyPage = lazy(() => import('@/features/daily/DailyPage'));
const TrafficPage = lazy(() => import('@/features/traffic/TrafficPage'));
const OkrPage = lazy(() => import('@/features/okr/OkrPage'));
const AdminPage = lazy(() => import('@/features/admin/AdminPage'));
const DailySubscriptionPage = lazy(() => import('@/features/subscription/DailySubscriptionPage'));
const OkrSubscriptionPage = lazy(() => import('@/features/subscription/OkrSubscriptionPage'));
const PeoplePage = lazy(() => import('@/features/people/PeoplePage'));
const GroupsPage = lazy(() => import('@/features/groups/GroupsPage'));
const ChatPage = lazy(() => import('@/features/chat/ChatPage'));
const InspirationsPage = lazy(() => import('@/features/workspace/WorkspacePages').then((module) => ({ default: module.InspirationsPage })));
const DocumentsPage = lazy(() => import('@/features/workspace/WorkspacePages').then((module) => ({ default: module.DocumentsPage })));
const DocumentEditorPage = lazy(() => import('@/features/workspace/WorkspacePages').then((module) => ({ default: module.DocumentEditorPage })));
const KnowledgePage = lazy(() => import('@/features/workspace/WorkspacePages').then((module) => ({ default: module.KnowledgePage })));
const KnowledgeArticlePage = lazy(() => import('@/features/workspace/WorkspacePages').then((module) => ({ default: module.KnowledgeArticlePage })));
const DataTablesPage = lazy(() => import('@/features/workspace/WorkspacePages').then((module) => ({ default: module.DataTablesPage })));
const DataTableEditorPage = lazy(() => import('@/features/workspace/WorkspacePages').then((module) => ({ default: module.DataTableEditorPage })));

function LazyPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={<Spinner label="正在加载页面…" />}>{children}</Suspense>;
}

function HomeRedirect() {
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const destinations: Array<[string, string]> = [
    ['feature:daily', '/daily'],
    ['feature:traffic', '/traffic-light'],
    ['feature:okr', '/okr'],
    ['feature:group', '/groups'],
    ['admin:employee', '/admin'],
    ['admin:department', '/admin'],
    ['admin:ai', '/admin'],
    ['admin:agent', '/admin'],
    ['admin:settings', '/admin'],
    ['admin:notification', '/admin'],
  ];
  const destination = destinations.find(([permission]) => hasPermission(permission))?.[1] ?? '/people/me';
  return <Navigate to={destination} replace />;
}

function AdminHomeRedirect() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const user = useAuthStore((state) => state.user);
  const location = useLocation();
  const legacyTab = new URLSearchParams(location.search).get('tab');
  const legacyDestinations: Record<string, [string, string]> = {
    employees: ['admin:employee', '/admin/employees'],
    departments: ['admin:department', '/admin/departments'],
    ai: ['admin:ai', '/admin/scoring-settings'],
  };
  if (legacyTab === 'knowledge' && user?.role === 'owner') {
    return <Navigate to="/admin/permissions" replace />;
  }
  const requested = legacyTab ? legacyDestinations[legacyTab] : undefined;
  if (requested && hasPermission(requested[0])) return <Navigate to={requested[1]} replace />;

  const destinations: Array<[string, string]> = [
    ['admin:employee', '/admin/employees'],
    ['admin:department', '/admin/departments'],
    ['admin:ai', '/admin/scoring-settings'],
    ['admin:agent', '/admin/agent-settings'],
    ['admin:settings', '/admin/company-settings'],
    ['admin:notification', '/admin/notification-settings'],
  ];
  const destination = destinations.find(([permission]) => hasPermission(permission))?.[1] ?? '/people/me';
  return <Navigate to={destination} replace />;
}

// Gate: block until the initial /auth/me bootstrap resolves, then require an
// authenticated session. Unauthenticated users bounce to /login.
function RequireAuth() {
  const status = useAuthStore((s) => s.status);
  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner label="正在加载会话…" />
      </div>
    );
  }
  if (status === 'anonymous') return <Navigate to="/login" replace />;
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

// Per-route permission gate. Feature permissions apply by row even for owner;
// the store only bypasses admin:* checks. Passes if the user holds ANY listed.
function RequirePermission({ permissions }: { permissions: string[] }) {
  const hasPermission = useAuthStore((s) => s.hasPermission);
  if (!permissions.some((p) => hasPermission(p))) return <ForbiddenPage />;
  return <Outlet />;
}

function RequireOwner() {
  const user = useAuthStore((state) => state.user);
  if (user?.role !== 'owner') return <ForbiddenPage />;
  return <Outlet />;
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/login/callback', element: <CallbackPage /> },
  { path: '/chat/oauth/callback', element: <ChatOAuthCallbackPage /> },
  {
    element: <RequireAuth />,
    children: [
      { index: true, element: <HomeRedirect /> },
      { path: 'chat', element: <LazyPage><ChatPage /></LazyPage> },
      { path: 'inspirations', element: <LazyPage><InspirationsPage /></LazyPage> },
      { path: 'documents', element: <LazyPage><DocumentsPage /></LazyPage> },
      { path: 'documents/new', element: <LazyPage><DocumentEditorPage /></LazyPage> },
      { path: 'knowledge', element: <LazyPage><KnowledgePage /></LazyPage> },
      { path: 'knowledge/documents/:documentId', element: <LazyPage><KnowledgeArticlePage /></LazyPage> },
      { path: 'data-tables', element: <LazyPage><DataTablesPage /></LazyPage> },
      { path: 'data-tables/new', element: <LazyPage><DataTableEditorPage /></LazyPage> },
      {
        element: <RequirePermission permissions={['feature:daily']} />,
        children: [{ path: 'daily', element: <LazyPage><DailyPage /></LazyPage> }],
      },
      {
        element: <RequirePermission permissions={['feature:traffic']} />,
        children: [{ path: 'traffic-light', element: <LazyPage><TrafficPage /></LazyPage> }],
      },
      {
        element: <RequirePermission permissions={['feature:okr']} />,
        children: [{ path: 'okr', element: <LazyPage><OkrPage /></LazyPage> }],
      },
      {
        element: <RequirePermission permissions={['feature:group']} />,
        children: [{ path: 'groups', element: <LazyPage><GroupsPage /></LazyPage> }],
      },
      {
        element: <RequirePermission permissions={['feature:daily']} />,
        children: [{ path: 'subscription/daily', element: <LazyPage><DailySubscriptionPage /></LazyPage> }],
      },
      {
        element: <RequirePermission permissions={['feature:okr']} />,
        children: [{ path: 'subscription/okr', element: <LazyPage><OkrSubscriptionPage /></LazyPage> }],
      },
      { path: 'profile', element: <Navigate to="/people/me" replace /> },
      { path: 'people/me', element: <LazyPage><PeoplePage /></LazyPage> },
      { path: 'people/:userId', element: <LazyPage><PeoplePage /></LazyPage> },
      { path: 'admin', element: <AdminHomeRedirect /> },
      {
        element: <RequirePermission permissions={['admin:employee']} />,
        children: [
          { path: 'admin/employees', element: <LazyPage><AdminPage section="employees" /></LazyPage> },
          { path: 'admin/sync-history', element: <LazyPage><AdminPage section="sync-history" /></LazyPage> },
        ],
      },
      {
        element: <RequireOwner />,
        children: [
          { path: 'admin/permissions', element: <LazyPage><AdminPage section="permissions" /></LazyPage> },
        ],
      },
      {
        element: <RequirePermission permissions={['admin:department']} />,
        children: [
          { path: 'admin/departments', element: <LazyPage><AdminPage section="departments" /></LazyPage> },
        ],
      },
      {
        element: <RequirePermission permissions={['admin:ai']} />,
        children: [
          { path: 'admin/scoring-settings', element: <LazyPage><AdminPage section="scoring" /></LazyPage> },
          { path: 'admin/ai-settings', element: <Navigate to="/admin/scoring-settings" replace /> },
        ],
      },
      {
        element: <RequirePermission permissions={['admin:agent']} />,
        children: [
          { path: 'admin/agent-settings', element: <LazyPage><AdminPage section="agents" /></LazyPage> },
        ],
      },
      {
        element: <RequirePermission permissions={['admin:settings']} />,
        children: [
          { path: 'admin/company-settings', element: <LazyPage><AdminPage section="settings" /></LazyPage> },
        ],
      },
      {
        element: <RequirePermission permissions={['admin:notification']} />,
        children: [
          { path: 'admin/notification-settings', element: <LazyPage><AdminPage section="notifications" /></LazyPage> },
        ],
      },
      { path: 'overview', element: <Navigate to="/admin" replace /> },
      { path: 'employees', element: <Navigate to="/admin/employees" replace /> },
      { path: 'departments', element: <Navigate to="/admin/departments" replace /> },
      { path: 'knowledge-permissions', element: <Navigate to="/admin/permissions" replace /> },
      { path: 'data-table-library', element: <Navigate to="/admin" replace /> },
      { path: 'ai-agents', element: <Navigate to="/admin/agent-settings" replace /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]);
