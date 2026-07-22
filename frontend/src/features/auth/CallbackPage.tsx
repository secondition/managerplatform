import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { feishuCallback } from '@/api/auth';
import { ApiError } from '@/api/client';
import { useAuthStore } from '@/stores/authStore';
import Spinner from '@/components/ui/Spinner';

// Handles the Feishu OAuth redirect: /login/callback?code=...&state=...
// Exchanges the code for a session, then routes to /daily.
export default function CallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const [error, setError] = useState<string | null>(null);
  // StrictMode double-invokes effects in dev; the OAuth code is single-use, so
  // guard against a second exchange attempt.
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const code = params.get('code');
    const state = params.get('state');
    if (!code || !state) {
      setError('回调参数缺失（code / state）。');
      return;
    }

    feishuCallback(code, state)
      .then((data) => {
        setSession(data);
        navigate('/', { replace: true });
      })
      .catch((err) => {
        const msg = err instanceof ApiError ? err.message : '登录失败，请重试。';
        setError(msg);
      });
  }, [params, navigate, setSession]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-sm bg-white rounded-2xl p-7 text-center shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
          <p className="text-sm font-semibold text-red-600 mb-1">登录失败</p>
          <p className="text-xs text-zinc-500 mb-4">{error}</p>
          <button
            onClick={() => navigate('/login', { replace: true })}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-xs font-medium cursor-pointer transition-colors"
          >
            返回登录
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <Spinner label="正在完成飞书登录…" />
    </div>
  );
}
