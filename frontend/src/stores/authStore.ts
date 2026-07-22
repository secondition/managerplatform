import { create } from 'zustand';
import type { AuthUserResponse, UserOut } from '@/types/api';

// Holds only identity + permissions in memory. Tokens live in httpOnly cookies
// and are never exposed to JS (see api/client.ts). `status` drives the router:
// 'loading' until the initial /auth/me bootstrap resolves.
type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

interface AuthState {
  status: AuthStatus;
  user: UserOut | null;
  permissions: string[];
  setSession: (data: AuthUserResponse) => void;
  updateUser: (patch: Partial<UserOut>) => void;
  clearSession: () => void;
  setAnonymous: () => void;
  hasPermission: (permission: string) => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  status: 'loading',
  user: null,
  permissions: [],
  setSession: (data) =>
    set({ status: 'authenticated', user: data.user, permissions: data.permissions }),
  updateUser: (patch) =>
    set((state) => ({ user: state.user ? { ...state.user, ...patch } : state.user })),
  clearSession: () => set({ status: 'anonymous', user: null, permissions: [] }),
  setAnonymous: () => set({ status: 'anonymous', user: null, permissions: [] }),
  hasPermission: (permission) => {
    const { user, permissions } = get();
    // Owner always has advanced (admin:*) access so they can't lock themselves
    // out of the backend, but feature:* is by row — owner toggles their own.
    if (user?.role === 'owner' && permission.startsWith('admin:')) return true;
    return permissions.includes(permission);
  },
}));
