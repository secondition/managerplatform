import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap } from 'lucide-react';
import { getLoginConfig } from '@/api/auth';
import { useAuthStore } from '@/stores/authStore';
import type { FeishuLoginConfig } from '@/types/api';
import { usePublicSettings } from '@/features/settings/hooks';
import { CultureWordCloudTemplate } from './wordcloud/CultureWordCloudTemplate';

// Single login path: redirect to Feishu's hosted authorize page (new v2 OAuth).
// The backend builds the authorize URL (with a signed state); we send the whole
// window there. Feishu redirects back to /login/callback?code&state, which
// CallbackPage exchanges for a session.
export default function LoginPage() {
  const navigate = useNavigate();
  const status = useAuthStore((s) => s.status);

  const [config, setConfig] = useState<FeishuLoginConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const companySettings = usePublicSettings();
  const companyName = companySettings.data?.company_name ?? 'Manager Platform';
  const logoUrl = companySettings.data?.logo_url;

  // Already signed in → skip the login page.
  useEffect(() => {
    if (status === 'authenticated') navigate('/', { replace: true });
  }, [status, navigate]);

  useEffect(() => {
    getLoginConfig()
      .then(setConfig)
      .catch(() => setError('无法获取登录配置，请确认后端服务已启动。'));
  }, []);

  const handleLogin = () => {
    if (config) window.location.href = config.authorize_url;
  };

  return (
    <div className="min-h-screen flex items-center justify-center lg:justify-end px-4 lg:pr-[8vw] xl:pr-[10vw] relative overflow-hidden">
      <CultureWordCloudTemplate />
      <div className="relative z-10 w-full max-w-sm bg-white rounded-2xl p-7 border border-zinc-100 shadow-[0_2px_12px_rgb(0,0,0,0.05)] animate-fade-in">
        <div className="flex flex-col items-center text-center gap-2 mb-6">
          {logoUrl ? (
            <img src={logoUrl} alt={companyName} className="w-11 h-11 rounded-2xl object-cover bg-white shadow-[0_4px_14px_rgba(37,99,235,0.18)]" />
          ) : (
            <span className="w-11 h-11 rounded-2xl bg-blue-600 text-white flex items-center justify-center shadow-[0_4px_14px_rgba(37,99,235,0.25)]">
              <Zap size={20} />
            </span>
          )}
          <h1 className="text-base font-bold text-zinc-900">{companyName}</h1>
          <p className="text-xs text-zinc-400">使用飞书登录，账号需已在企业通讯录同步花名册内。</p>
        </div>

        {error && (
          <div className="mb-4 text-[11px] text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <button
          onClick={handleLogin}
          disabled={!config}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed text-white px-4 py-2.5 rounded-lg text-sm font-medium cursor-pointer transition-colors"
        >
          {config ? '使用飞书登录' : '正在加载…'}
        </button>
      </div>
    </div>
  );
}
