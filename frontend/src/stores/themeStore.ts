import { useEffect } from 'react';
import { create } from 'zustand';

export type ThemeAccent = 'blue' | 'emerald' | 'amber' | 'rose' | 'violet';
export type ThemeFont = 'system' | 'yahei' | 'serif';
export type ThemeSize = 'compact' | 'standard' | 'large';

interface ThemePreferences {
  accent: ThemeAccent;
  font: ThemeFont;
  size: ThemeSize;
}

interface ThemeState extends ThemePreferences {
  update: (patch: Partial<ThemePreferences>) => void;
  reset: () => void;
}

const STORAGE_KEY = 'managerplatform-theme';
const DEFAULT_THEME: ThemePreferences = {
  accent: 'blue',
  font: 'system',
  size: 'standard',
};

function readTheme(): ThemePreferences {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as Partial<ThemePreferences>;
    return {
      accent: ['blue', 'emerald', 'amber', 'rose', 'violet'].includes(stored.accent ?? '')
        ? stored.accent as ThemeAccent
        : DEFAULT_THEME.accent,
      font: ['system', 'yahei', 'serif'].includes(stored.font ?? '')
        ? stored.font as ThemeFont
        : DEFAULT_THEME.font,
      size: ['compact', 'standard', 'large'].includes(stored.size ?? '')
        ? stored.size as ThemeSize
        : DEFAULT_THEME.size,
    };
  } catch {
    return DEFAULT_THEME;
  }
}

function saveTheme(theme: ThemePreferences) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(theme));
}

const initialTheme = readTheme();

export const useThemeStore = create<ThemeState>((set) => ({
  ...initialTheme,
  update: (patch) => set((state) => {
    const next = { accent: state.accent, font: state.font, size: state.size, ...patch };
    saveTheme(next);
    return next;
  }),
  reset: () => set(() => {
    saveTheme(DEFAULT_THEME);
    return DEFAULT_THEME;
  }),
}));

export function useApplyTheme() {
  const accent = useThemeStore((state) => state.accent);
  const font = useThemeStore((state) => state.font);
  const size = useThemeStore((state) => state.size);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.themeAccent = accent;
    root.dataset.themeFont = font;
    root.dataset.themeSize = size;
  }, [accent, font, size]);
}
