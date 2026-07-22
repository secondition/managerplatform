import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as settingsApi from '@/api/settings';

export const publicSettingsKey = ['settings', 'public'] as const;
const companySettingsKey = ['settings', 'company'] as const;

export function usePublicSettings() {
  return useQuery({
    queryKey: publicSettingsKey,
    queryFn: settingsApi.getPublicCompanySettings,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCompanySettings() {
  return useQuery({
    queryKey: companySettingsKey,
    queryFn: settingsApi.getCompanySettings,
  });
}

function useInvalidateSettings() {
  const qc = useQueryClient();
  return (data?: unknown) => {
    qc.invalidateQueries({ queryKey: publicSettingsKey });
    qc.invalidateQueries({ queryKey: companySettingsKey });
    if (data) {
      qc.setQueryData(publicSettingsKey, data);
      qc.setQueryData(companySettingsKey, data);
    }
  };
}

export function useUpdateCompanySettings() {
  const invalidate = useInvalidateSettings();
  return useMutation({
    mutationFn: settingsApi.updateCompanySettings,
    onSuccess: invalidate,
  });
}

export function useUploadCompanyLogo() {
  const invalidate = useInvalidateSettings();
  return useMutation({
    mutationFn: settingsApi.uploadCompanyLogo,
    onSuccess: invalidate,
  });
}
