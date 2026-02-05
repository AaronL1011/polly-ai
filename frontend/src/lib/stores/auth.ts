import { writable, derived, get } from 'svelte/store';
import type { User, Session } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured } from '$lib/supabase';

// Types
export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: 'owner' | 'admin' | 'member' | 'viewer';
  billing_email: string;
  plan: string;
  member_count?: number;
}

export interface BillingAccount {
  id: string;
  account_type: 'user' | 'organization';
  credits: number;
  free_tier_remaining: number;
  free_tier_reset_at: string | null;
  lifetime_credits: number;
  lifetime_usage: number;
  has_stripe_customer: boolean;
}

interface AuthState {
  user: User | null;
  session: Session | null;
  organizations: Organization[];
  activeContext: 'personal' | string; // 'personal' or org UUID
  loading: boolean;
  initialized: boolean;
}

const initialState: AuthState = {
  user: null,
  session: null,
  organizations: [],
  activeContext: 'personal',
  loading: true,
  initialized: false,
};

function createAuthStore() {
  const { subscribe, set, update } = writable<AuthState>(initialState);

  // Initialize auth state and listen for changes
  async function initialize() {
    if (!isSupabaseConfigured()) {
      update((state) => ({ ...state, loading: false, initialized: true }));
      return;
    }

    // Get initial session
    const { data: { session } } = await supabase.auth.getSession();
    
    if (session?.user) {
      await handleAuthChange(session);
    } else {
      update((state) => ({ ...state, loading: false, initialized: true }));
    }

    // Listen for auth state changes
    supabase.auth.onAuthStateChange(async (event, session) => {
      if (event === 'SIGNED_IN' && session) {
        await handleAuthChange(session);
      } else if (event === 'SIGNED_OUT') {
        set({ ...initialState, loading: false, initialized: true });
      } else if (event === 'TOKEN_REFRESHED' && session) {
        update((state) => ({ ...state, session }));
      }
    });
  }

  // Handle auth state change - fetch user organizations
  async function handleAuthChange(session: Session) {
    update((state) => ({ ...state, user: session.user, session, loading: true }));

    try {
      // Fetch user's organizations from our API
      const orgs = await fetchOrganizations(session.access_token);
      update((state) => ({
        ...state,
        organizations: orgs,
        loading: false,
        initialized: true,
      }));
    } catch (error) {
      console.error('Failed to fetch organizations:', error);
      update((state) => ({ ...state, loading: false, initialized: true }));
    }
  }

  // Fetch organizations from API
  async function fetchOrganizations(token: string): Promise<Organization[]> {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    try {
      const response = await fetch(`${apiUrl}/orgs`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      if (!response.ok) return [];
      return await response.json();
    } catch {
      return [];
    }
  }

  // Sign in with email and password
  async function signIn(email: string, password: string): Promise<{ error: string | null }> {
    if (!isSupabaseConfigured()) {
      return { error: 'Authentication is not configured' };
    }

    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      return { error: error.message };
    }
    return { error: null };
  }

  // Sign up with email and password
  async function signUp(email: string, password: string): Promise<{ error: string | null }> {
    if (!isSupabaseConfigured()) {
      return { error: 'Authentication is not configured' };
    }

    const { error } = await supabase.auth.signUp({ email, password });
    if (error) {
      return { error: error.message };
    }
    return { error: null };
  }

  // Sign out
  async function signOut(): Promise<void> {
    if (!isSupabaseConfigured()) return;
    await supabase.auth.signOut();
  }

  // Switch active context (personal or organization)
  function switchContext(context: 'personal' | string) {
    update((state) => ({ ...state, activeContext: context }));
  }

  // Refresh organizations list
  async function refreshOrganizations() {
    const state = get({ subscribe });
    if (!state.session) return;
    
    const orgs = await fetchOrganizations(state.session.access_token);
    update((s) => ({ ...s, organizations: orgs }));
  }

  return {
    subscribe,
    initialize,
    signIn,
    signUp,
    signOut,
    switchContext,
    refreshOrganizations,
  };
}

export const authStore = createAuthStore();

// Derived stores for convenience
export const isAuthenticated = derived(authStore, ($auth) => $auth.user !== null);

export const currentUser = derived(authStore, ($auth) => $auth.user);

export const accessToken = derived(authStore, ($auth) => $auth.session?.access_token ?? null);

export const activeOrganization = derived(authStore, ($auth) => {
  if ($auth.activeContext === 'personal') return null;
  return $auth.organizations.find((org) => org.id === $auth.activeContext) ?? null;
});

export const currentContextName = derived(
  [authStore, activeOrganization],
  ([$auth, $activeOrg]) => {
    if ($activeOrg) return $activeOrg.name;
    if ($auth.user) return 'Personal Account';
    return 'Anonymous';
  }
);

export const activeContextId = derived(authStore, ($auth) => {
  return $auth.activeContext === 'personal' ? null : $auth.activeContext;
});
