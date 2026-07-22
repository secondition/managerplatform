import { useEffect } from 'react';
import { getMe } from '@/api/auth';
import { ApiError, SESSION_EXPIRED_EVENT } from '@/api/client';
import { useAuthStore } from '@/stores/authStore';

// Runs once at app start: hydrate the session from the httpOnly cookie via
// /auth/me. Also listens for the client's session-expired broadcast (fired when
// a silent refresh fails) and drops the store to anonymous so guards redirect.
export function useBootstrapAuth(): void {
  const setSession = useAuthStore((s) => s.setSession);
  const setAnonymous = useAuthStore((s) => s.setAnonymous);

  useEffect(() => {
    let cancelled = false;

    // Local visual-regression mode. Vite removes this branch from production;
    // it exists so authenticated workspace screens can be reviewed without a
    // Feishu callback while developing them on localhost.
    if (import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === '1') {
      setSession({
        user: {
          id: 1,
          name: '故障机器人',
          email: 'preview@example.com',
          avatar_url: null,
          role: 'owner',
          department_id: null,
          status: 'active',
          last_login_at: null,
        },
        permissions: [
          'feature:daily',
          'feature:traffic',
          'feature:okr',
          'feature:group',
          'admin:employee',
          'admin:department',
          'admin:settings',
          'admin:ai',
        ],
        csrf_token: null,
      });
      return;
    }

    getMe()
      .then((data) => {
        if (!cancelled) setSession(data);
      })
      .catch((err) => {
        // 401 is the expected "not logged in yet" path; anything else we still
        // treat as anonymous but let it surface in the console.
        if (!cancelled) setAnonymous();
        if (!(err instanceof ApiError) || err.status !== 401) {
          console.warn('Auth bootstrap failed:', err);
        }
      });

    const onExpired = () => setAnonymous();
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => {
      cancelled = true;
      window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
    };
  }, [setSession, setAnonymous]);
}

