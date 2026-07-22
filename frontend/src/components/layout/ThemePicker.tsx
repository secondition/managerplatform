import { useRef, useState } from 'react';
import { Check, Palette, RotateCcw, Type } from 'lucide-react';
import AnchoredPopover from '@/components/ui/AnchoredPopover';
import {
  useThemeStore,
  type ThemeAccent,
  type ThemeFont,
  type ThemeSize,
} from '@/stores/themeStore';

const ACCENTS: { value: ThemeAccent; label: string; color: string }[] = [
  { value: 'blue', label: '海蓝', color: '#2563eb' },
  { value: 'emerald', label: '青绿', color: '#059669' },
  { value: 'amber', label: '琥珀', color: '#d97706' },
  { value: 'rose', label: '玫红', color: '#e11d48' },
  { value: 'violet', label: '紫罗兰', color: '#7c3aed' },
];

const FONTS: { value: ThemeFont; label: string; sampleClass: string }[] = [
  { value: 'system', label: '系统默认', sampleClass: 'font-sans' },
  { value: 'yahei', label: '微软雅黑', sampleClass: 'font-sans' },
  { value: 'serif', label: '宋体', sampleClass: 'font-serif' },
];

const SIZES: { value: ThemeSize; label: string; detail: string }[] = [
  { value: 'compact', label: '紧凑', detail: '更高信息密度' },
  { value: 'standard', label: '标准', detail: '默认布局尺寸' },
  { value: 'large', label: '舒展', detail: '更大文字与卡片' },
];

export default function ThemePicker() {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const accent = useThemeStore((state) => state.accent);
  const font = useThemeStore((state) => state.font);
  const size = useThemeStore((state) => state.size);
  const update = useThemeStore((state) => state.update);
  const reset = useThemeStore((state) => state.reset);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label="主题设置"
        aria-expanded={open}
        className={`rounded-lg p-1.5 transition-colors hover:bg-slate-50 ${open ? 'bg-slate-100' : ''}`}
        title="主题设置"
      >
        <Palette size={15} className="theme-icon-color" />
      </button>

      <AnchoredPopover
        anchor={open ? triggerRef.current : null}
        width={320}
        align="end"
        zIndex={1200}
        borderRadius={16}
        closeOnScroll
        onClose={() => setOpen(false)}
      >
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">界面主题</h3>
              <p className="mt-0.5 text-[11px] text-slate-400">设置会自动保存在当前浏览器</p>
            </div>
            <button type="button" onClick={reset} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] text-slate-400 hover:bg-slate-50 hover:text-slate-700">
              <RotateCcw size={12} />恢复默认
            </button>
          </div>

          <ThemeSection title="界面强调色" icon={<Palette size={13} />}>
            <div className="grid grid-cols-5 gap-2">
              {ACCENTS.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => update({ accent: item.value })}
                  className={`flex h-10 items-center justify-center rounded-xl border ${accent === item.value ? 'border-slate-700 bg-slate-50' : 'border-slate-100 hover:border-slate-300'}`}
                  title={item.label}
                  aria-label={`图标颜色：${item.label}`}
                >
                  <span style={{ backgroundColor: item.color }} className="flex h-5 w-5 items-center justify-center rounded-full text-white">
                    {accent === item.value && <Check size={12} />}
                  </span>
                </button>
              ))}
            </div>
          </ThemeSection>

          <ThemeSection title="界面字体" icon={<Type size={13} />}>
            <div className="grid grid-cols-3 gap-2">
              {FONTS.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => update({ font: item.value })}
                  className={`h-10 rounded-xl border text-[12px] ${item.sampleClass} ${font === item.value ? 'border-[var(--theme-accent)] bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]' : 'border-slate-200 text-slate-600 hover:border-slate-300'}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </ThemeSection>

          <ThemeSection title="字体与卡片大小" icon={<Type size={13} />}>
            <div className="grid grid-cols-3 gap-2">
              {SIZES.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => update({ size: item.value })}
                  className={`rounded-xl border px-2 py-2 text-left ${size === item.value ? 'border-[var(--theme-accent)] bg-[var(--theme-accent-soft)]' : 'border-slate-200 hover:border-slate-300'}`}
                >
                  <strong className={`block text-[12px] ${size === item.value ? 'text-[var(--theme-accent)]' : 'text-slate-700'}`}>{item.label}</strong>
                  <span className="mt-0.5 block text-[10px] text-slate-400">{item.detail}</span>
                </button>
              ))}
            </div>
          </ThemeSection>
        </div>
      </AnchoredPopover>
    </>
  );
}

function ThemeSection({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="mt-4">
      <h4 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold text-slate-600">{icon}{title}</h4>
      {children}
    </section>
  );
}
