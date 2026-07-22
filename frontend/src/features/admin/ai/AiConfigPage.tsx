import { Sparkles } from 'lucide-react';
import Spinner from '@/components/ui/Spinner';
import AiProviderForm from './AiProviderForm';
import AiFeatureToggles from './AiFeatureToggles';
import PromptConfigPanel from './PromptConfigPanel';
import { useAiProvider, useUpdateAiProvider } from './hooks';

export default function AiConfigPage() {
  const provider = useAiProvider();
  const update = useUpdateAiProvider();

  const enabled = provider.data?.enabled ?? false;

  return (
    <div className="space-y-5">
      <section className="bg-white rounded-2xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-[var(--theme-accent-soft)] text-[var(--theme-icon-color)]">
              <Sparkles size={15} />
            </span>
            <div>
              <h3 className="text-sm font-bold text-zinc-900">启用评分服务</h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                {enabled ? '已启用，可在下方配置评分接口、开关与提示词。' : '关闭状态下评分与建议功能显示未启用。'}
              </p>
            </div>
          </div>

          {provider.isLoading ? (
            <Spinner />
          ) : (
            <button
              type="button"
              role="switch"
              aria-checked={enabled}
              onClick={() => update.mutate({ enabled: !enabled })}
              disabled={update.isPending}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 cursor-pointer ${
                enabled ? 'bg-[var(--theme-accent)]' : 'bg-zinc-200'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          )}
        </div>
      </section>

      {enabled && (
        <>
          <AiProviderForm />
          <AiFeatureToggles />
          <PromptConfigPanel />
        </>
      )}
    </div>
  );
}
