import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as peopleApi from '@/api/people';

export const personProfileKey = (userId: number | 'me', month: string) =>
  ['people', userId, month] as const;

export function usePersonProfile(userId: number | 'me', month: string) {
  return useQuery({
    queryKey: personProfileKey(userId, month),
    placeholderData: keepPreviousData,
    queryFn: () =>
      userId === 'me'
        ? peopleApi.getMyProfile(month)
        : peopleApi.getPersonProfile(userId, month),
  });
}

export function useSubscribePerson(userId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => peopleApi.subscribePerson(userId as number),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['people'] });
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
    },
  });
}

export function useUnsubscribePerson(userId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => peopleApi.unsubscribePerson(userId as number),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['people'] });
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
    },
  });
}

export function useUpdateMySignature() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: peopleApi.updateMySignature,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['people'] });
    },
  });
}

