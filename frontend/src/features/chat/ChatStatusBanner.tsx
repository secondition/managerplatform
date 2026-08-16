import { Clock3, Info, TriangleAlert } from 'lucide-react';
import type { ChatStateBanner as ChatStateBannerData } from './chatState';

const TONE_CLASSES = {
  neutral: 'border-slate-200 bg-slate-50 text-slate-600',
  info: 'border-blue-200 bg-blue-50 text-blue-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  danger: 'border-rose-200 bg-rose-50 text-rose-700',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
};

export default function ChatStatusBanner({ banner }: { banner: ChatStateBannerData }) {
  const Icon = banner.tone === 'warning' ? Clock3 : banner.tone === 'danger' ? TriangleAlert : Info;

  return (
    <div className={`mx-4 mt-4 flex shrink-0 gap-2.5 rounded-xl border px-3.5 py-3 sm:mx-5 ${TONE_CLASSES[banner.tone]}`} role="status">
      <Icon size={15} className="mt-0.5 shrink-0" />
      <div>
        <strong className="block text-[11px] font-semibold">{banner.title}</strong>
        <p className="mt-0.5 text-[10px] leading-4 opacity-80">{banner.description}</p>
      </div>
    </div>
  );
}
