import type { PersonProfileOut, PersonSubscriptionOut } from '@/types/api';
import { api } from './client';

export function getMyProfile(month: string): Promise<PersonProfileOut> {
  return api<PersonProfileOut>(`/people/me?month=${encodeURIComponent(month)}`);
}

export function getPersonProfile(userId: number, month: string): Promise<PersonProfileOut> {
  return api<PersonProfileOut>(`/people/${userId}?month=${encodeURIComponent(month)}`);
}

export function subscribePerson(userId: number): Promise<PersonSubscriptionOut> {
  return api<PersonSubscriptionOut>(`/people/${userId}/subscribe`, { method: 'POST' });
}

export function unsubscribePerson(userId: number): Promise<null> {
  return api<null>(`/people/${userId}/subscribe`, { method: 'DELETE' });
}

export function updateMySignature(profileSignature: string): Promise<PersonProfileOut> {
  return api<PersonProfileOut>('/people/me/signature', {
    method: 'PATCH',
    body: { profile_signature: profileSignature },
  });
}

