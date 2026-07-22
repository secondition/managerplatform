import type {
  AiFeatureFlagsOut,
  AiProviderOut,
  AiProviderTestOut,
  AiTaskOut,
  PromptConfigOut,
} from '@/types/api';
import { api } from './client';

// ---- admin: provider ----

export function getAiProvider(): Promise<AiProviderOut> {
  return api<AiProviderOut>('/admin/ai/provider');
}

export interface UpdateAiProviderInput {
  provider?: string;
  api_base?: string;
  default_model?: string;
  enabled?: boolean;
  // undefined = keep existing key; '' = clear; string = replace.
  api_key?: string;
}

export function updateAiProvider(input: UpdateAiProviderInput): Promise<AiProviderOut> {
  return api<AiProviderOut>('/admin/ai/provider', { method: 'PATCH', body: input });
}

export function testAiProvider(): Promise<AiProviderTestOut> {
  return api<AiProviderTestOut>('/admin/ai/provider/test', { method: 'POST' });
}

// ---- user-facing: feature flags (read-only, gates page panels) ----

export function getAiFeatureFlags(): Promise<AiFeatureFlagsOut> {
  return api<AiFeatureFlagsOut>('/ai/features');
}

// ---- admin: feature flags ----

export function getAiFeatures(): Promise<AiFeatureFlagsOut> {
  return api<AiFeatureFlagsOut>('/admin/ai/features');
}

export function updateAiFeatures(
  input: Partial<AiFeatureFlagsOut>,
): Promise<AiFeatureFlagsOut> {
  return api<AiFeatureFlagsOut>('/admin/ai/features', { method: 'PATCH', body: input });
}

// ---- admin: prompts ----

export function getAiPrompts(): Promise<PromptConfigOut[]> {
  return api<PromptConfigOut[]>('/admin/ai/prompts');
}

export interface UpdatePromptInput {
  name?: string;
  template_content?: string;
  version?: string;
  variables?: string[];
}

export function updateAiPrompt(
  promptType: string,
  input: UpdatePromptInput,
): Promise<PromptConfigOut> {
  return api<PromptConfigOut>(`/admin/ai/prompts/${promptType}`, {
    method: 'PATCH',
    body: input,
  });
}

export function restoreAiPromptDefault(promptType: string): Promise<PromptConfigOut> {
  return api<PromptConfigOut>(`/admin/ai/prompts/${promptType}/restore-default`, {
    method: 'POST',
  });
}

// ---- ai tasks ----

export function getAiTasks(): Promise<AiTaskOut[]> {
  return api<AiTaskOut[]>('/ai/tasks');
}
