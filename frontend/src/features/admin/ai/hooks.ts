import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as aiApi from '@/api/ai';
import type { UpdateAiProviderInput, UpdatePromptInput } from '@/api/ai';
import type { AiFeatureFlagsOut } from '@/types/api';

const providerKey = ['admin-ai-provider'] as const;
const featuresKey = ['admin-ai-features'] as const;
const promptsKey = ['admin-ai-prompts'] as const;

export function useAiProvider() {
  return useQuery({ queryKey: providerKey, queryFn: aiApi.getAiProvider });
}

export function useUpdateAiProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateAiProviderInput) => aiApi.updateAiProvider(input),
    onSuccess: (data) => qc.setQueryData(providerKey, data),
  });
}

export function useTestAiProvider() {
  return useMutation({ mutationFn: () => aiApi.testAiProvider() });
}

export function useAiFeatures() {
  return useQuery({ queryKey: featuresKey, queryFn: aiApi.getAiFeatures });
}

export function useUpdateAiFeatures() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Partial<AiFeatureFlagsOut>) => aiApi.updateAiFeatures(input),
    onSuccess: (data) => {
      qc.setQueryData(featuresKey, data);
      // Also drop the user-facing copy that gates the daily/OKR panels.
      qc.invalidateQueries({ queryKey: ['ai-feature-flags'] });
    },
  });
}

export function useAiPrompts() {
  return useQuery({ queryKey: promptsKey, queryFn: aiApi.getAiPrompts });
}

export function useUpdateAiPrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ promptType, input }: { promptType: string; input: UpdatePromptInput }) =>
      aiApi.updateAiPrompt(promptType, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: promptsKey }),
  });
}

export function useRestoreAiPrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (promptType: string) => aiApi.restoreAiPromptDefault(promptType),
    onSuccess: () => qc.invalidateQueries({ queryKey: promptsKey }),
  });
}
