import { useEffect, useState } from 'react';
import { Cpu, Loader2, Save, Plug, CheckCircle2, XCircle, Eye, EyeOff } from 'lucide-react';
import Spinner from '@/components/ui/Spinner';
import { useAiProvider, useUpdateAiProvider, useTestAiProvider } from './hooks';

const INTERFACES = [
  { value: 'openai_chat', label: 'OpenAI（chat）' },
  { value: 'openai_response', label: 'OpenAI（response）' },
  { value: 'anthropic', label: 'anthropic' },
];

export default function AiProviderForm() {
  const provider = useAiProvider();
  const update = useUpdateAiProvider();
  const test = useTestAiProvider();

  const [kind, setKind] = useState('openai_chat');
  const [apiBase, setApiBase] = useState('');
  const [model, setModel] = useState('');
  // '' means "keep existing"; a non-empty value replaces the key on save.
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    if (!provider.data) return;
    setKind(provider.data.provider || 'openai_chat');
    setApiBase(provider.data.api_base);
    setModel(provider.data.default_model);
    setApiKey('');
  }, [provider.data]);

  const handleSave = () => {
    update.mutate({
      provider: kind,
      api_base: apiBase.trim(),
      default_model: model.trim(),
      ...(apiKey ? { api_key: apiKey } : {}),
    });
  };

  if (provider.isLoading) return <Spinner label="加载评分接口配置..." />;

  const keyPlaceholder = provider.data?.api_key_set
    ? `已配置（${provider.data.api_key_masked}），留空则不修改`
    : '输入 API Key';

  return (
    <section className="bg-white rounded-2xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="flex items-center gap-2 mb-5">
        <span className="p-1.5 rounded-lg bg-[var(--theme-accent-soft)] text-[var(--theme-icon-color)]">
          <Cpu size={15} />
        </span>
        <div>
          <h3 className="text-sm font-bold text-zinc-900">评分服务接口</h3>
          <p className="text-xs text-zinc-400 mt-0.5">配置接口类型、密钥与模型。密钥加密存储、仅脱敏回显。</p>
        </div>
      </div>

      <div className="space-y-4 max-w-xl">
        <label className="block">
          <span className="text-xs font-medium text-zinc-700">接口类型</span>
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-800 outline-none focus:border-[var(--theme-accent)]"
          >
            {INTERFACES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-zinc-700">API Base URL</span>
          <input
            value={apiBase}
            onChange={(e) => setApiBase(e.target.value)}
            className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-800 outline-none focus:border-[var(--theme-accent)]"
            placeholder="留空则用接口默认地址"
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-zinc-700">模型名称</span>
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-800 outline-none focus:border-[var(--theme-accent)]"
            placeholder="如 gpt-4o、deepseek-chat、claude-sonnet-4"
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-zinc-700">API Key</span>
          <div className="relative mt-1.5">
            <input
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              autoComplete="new-password"
              className="w-full rounded-xl border border-zinc-200 bg-white pl-3 pr-10 py-2 text-sm text-zinc-800 outline-none focus:border-[var(--theme-accent)]"
              placeholder={keyPlaceholder}
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              title={showKey ? '隐藏' : '显示'}
              className="absolute inset-y-0 right-0 flex items-center px-3 text-zinc-400 hover:text-zinc-600 cursor-pointer"
            >
              {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </label>

        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={handleSave}
            disabled={update.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--theme-accent)] px-4 py-2 text-xs font-semibold text-white hover:bg-[var(--theme-accent-hover)] disabled:opacity-50 cursor-pointer"
          >
            {update.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            保存配置
          </button>
          <button
            onClick={() => test.mutate()}
            disabled={test.isPending}
            className="inline-flex items-center gap-2 rounded-xl border border-zinc-200 px-4 py-2 text-xs font-semibold text-zinc-700 hover:border-[var(--theme-accent)] hover:text-[var(--theme-accent)] disabled:opacity-50 cursor-pointer"
          >
            {test.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plug size={14} />}
            测试连通
          </button>
        </div>

        {update.isSuccess && !update.isPending && (
          <p className="text-[11px] text-emerald-600">配置已保存。</p>
        )}
        {test.data && (
          <p
            className={`flex items-center gap-1.5 text-[11px] ${
              test.data.ok ? 'text-emerald-600' : 'text-red-500'
            }`}
          >
            {test.data.ok ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
            {test.data.message}
          </p>
        )}
      </div>
    </section>
  );
}
