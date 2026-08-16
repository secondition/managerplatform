import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Spinner from '@/components/ui/Spinner';
import { completeChatAuthorization } from '@/api/chat';

export default function ChatOAuthCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const code = params.get('code');
    const state = params.get('state');
    const oauthError = params.get('error');
    window.history.replaceState(null, '', window.location.pathname);

    if (oauthError || !code || !state) {
      setError('飞书授权未完成，请返回 AI 大脑重新授权。');
      return;
    }

    completeChatAuthorization(code, state)
      .then((result) => {
        navigate(result.return_to, { replace: true });
      })
      .catch(() => {
        setError('授权校验失败或已失效，请返回 AI 大脑重新授权。');
      });
  }, [navigate, params]);

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 py-12">
        <section className="w-full max-w-md rounded-2xl border border-red-100 bg-white p-7 text-center shadow-sm">
          <p className="text-sm font-semibold text-red-600">聊天授权未完成</p>
          <p className="mt-2 text-xs leading-5 text-zinc-500">{error}</p>
          <button
            type="button"
            onClick={() => navigate('/chat', { replace: true })}
            className="mt-5 rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-zinc-700"
          >
            返回 AI 大脑
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50">
      <Spinner label="正在完成飞书聊天授权…" />
    </main>
  );
}
