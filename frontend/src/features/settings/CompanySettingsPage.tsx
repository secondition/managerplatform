import { useEffect, useState } from 'react';
import { Building2, ImageUp, Loader2, Save } from 'lucide-react';
import Spinner from '@/components/ui/Spinner';
import { useCompanySettings, useUpdateCompanySettings, useUploadCompanyLogo } from './hooks';

export default function CompanySettingsPage() {
  const settings = useCompanySettings();
  const update = useUpdateCompanySettings();
  const uploadLogo = useUploadCompanyLogo();
  const [companyName, setCompanyName] = useState('');
  const [footerText, setFooterText] = useState('');

  useEffect(() => {
    if (!settings.data) return;
    setCompanyName(settings.data.company_name);
    setFooterText(settings.data.footer_text);
  }, [settings.data]);

  const handleSave = () => {
    if (!companyName.trim() || !footerText.trim()) return;
    update.mutate({
      company_name: companyName.trim(),
      footer_text: footerText.trim(),
    });
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-5">
      <section className="bg-white rounded-2xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
        <div className="flex items-center gap-2 mb-5">
          <span className="p-1.5 rounded-lg bg-[var(--theme-accent-soft)] text-[var(--theme-icon-color)]">
            <Building2 size={15} />
          </span>
          <div>
            <h3 className="text-sm font-bold text-zinc-900">企业设置</h3>
            <p className="text-xs text-zinc-400 mt-0.5">配置平台品牌信息，会同步影响顶栏与页脚展示。</p>
          </div>
        </div>

        {settings.isLoading ? (
          <Spinner label="加载企业设置..." />
        ) : (
          <div className="space-y-4">
            <label className="block">
              <span className="text-xs font-medium text-zinc-700">企业名称</span>
              <input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value.slice(0, 100))}
                className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-800 outline-none focus:border-[var(--theme-accent)]"
                placeholder="Manager Platform"
              />
            </label>

            <label className="block">
              <span className="text-xs font-medium text-zinc-700">页脚文案</span>
              <input
                value={footerText}
                onChange={(e) => setFooterText(e.target.value.slice(0, 200))}
                className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-800 outline-none focus:border-[var(--theme-accent)]"
                placeholder="MANAGER PLATFORM · Open Source Work Management"
              />
            </label>

            <button
              onClick={handleSave}
              disabled={!companyName.trim() || !footerText.trim() || update.isPending}
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--theme-accent)] px-4 py-2 text-xs font-semibold text-white hover:bg-[var(--theme-accent-hover)] disabled:opacity-50 cursor-pointer"
            >
              {update.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              保存设置
            </button>
          </div>
        )}
      </section>

      <section className="bg-white rounded-2xl p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
        <h3 className="text-sm font-bold text-zinc-900 mb-4">Logo 图像</h3>
        <div className="rounded-xl border border-zinc-100 bg-zinc-50 p-4 flex items-center gap-3">
          {settings.data?.logo_url ? (
            <img
              src={settings.data.logo_url}
              alt={settings.data.company_name}
              className="w-12 h-12 rounded-xl object-cover bg-white border border-zinc-100"
            />
          ) : (
            <span className="w-12 h-12 rounded-xl bg-blue-600 text-white flex items-center justify-center">
              <Building2 size={20} />
            </span>
          )}
          <div className="min-w-0">
            <div className="text-xs font-semibold text-zinc-800 truncate">{settings.data?.company_name}</div>
            <p className="text-[11px] text-zinc-400 mt-1">支持 PNG、JPG、WEBP，最大 2MB。</p>
          </div>
        </div>

        <label className="mt-4 inline-flex items-center gap-2 rounded-xl border border-zinc-200 px-4 py-2 text-xs font-semibold text-zinc-700 hover:border-[var(--theme-accent)] hover:text-[var(--theme-accent)] cursor-pointer">
          {uploadLogo.isPending ? <Loader2 size={14} className="animate-spin" /> : <ImageUp size={14} />}
          上传 Logo
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            disabled={uploadLogo.isPending}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadLogo.mutate(file);
              e.currentTarget.value = '';
            }}
          />
        </label>
      </section>
    </div>
  );
}
