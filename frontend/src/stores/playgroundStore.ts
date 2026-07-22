import { create } from 'zustand';

// Shared state for the floating avatar field: just whether it is enabled. The
// field is a fixed viewport overlay, so it no longer needs a scroll "basement".
const STORAGE_KEY = 'avatarField.enabled';

function readEnabled(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) !== 'off';
  } catch {
    return true;
  }
}

interface PlaygroundState {
  enabled: boolean;
  toggleEnabled: () => void;
}

export const usePlaygroundStore = create<PlaygroundState>((set) => ({
  enabled: readEnabled(),
  toggleEnabled: () =>
    set((state) => {
      const next = !state.enabled;
      try {
        localStorage.setItem(STORAGE_KEY, next ? 'on' : 'off');
      } catch {
        /* ignore storage errors */
      }
      return { enabled: next };
    }),
}));
