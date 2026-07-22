import type { AuthUserResponse, FeishuLoginConfig } from '@/types/api';
import { api } from './client';

export function getLoginConfig(): Promise<FeishuLoginConfig> {
  return api<FeishuLoginConfig>('/auth/feishu/login-config');
}

export function feishuCallback(code: string, state: string): Promise<AuthUserResponse> {
  return api<AuthUserResponse>('/auth/feishu/callback', {
    method: 'POST',
    body: { code, state },
  });
}

export function getMe(): Promise<AuthUserResponse> {
  return api<AuthUserResponse>('/auth/me');
}

export function logout(): Promise<{ ok: boolean }> {
  return api<{ ok: boolean }>('/auth/logout', { method: 'POST' });
}
