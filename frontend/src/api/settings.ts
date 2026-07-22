import type { CompanySettingOut } from '@/types/api';
import { api } from './client';

export interface CompanySettingInput {
  company_name: string;
  footer_text: string;
}

export function getPublicCompanySettings(): Promise<CompanySettingOut> {
  return api<CompanySettingOut>('/settings/public', { skipRefresh: true });
}

export function getCompanySettings(): Promise<CompanySettingOut> {
  return api<CompanySettingOut>('/settings/company');
}

export function updateCompanySettings(input: CompanySettingInput): Promise<CompanySettingOut> {
  return api<CompanySettingOut>('/settings/company', { method: 'PATCH', body: input });
}

export function uploadCompanyLogo(file: File): Promise<CompanySettingOut> {
  const form = new FormData();
  form.append('logo', file);
  return api<CompanySettingOut>('/settings/company/logo', {
    method: 'POST',
    body: form,
  });
}
