import { writable, derived } from 'svelte/store';
import { api, type QueryResponse, type QueryRequest } from '$lib/api/client';

interface QueryState {
  query: string;
  isLoading: boolean;
  error: string | null;
  response: QueryResponse | null;
  hasSubmitted: boolean;
}

function createQueryStore() {
  const { subscribe, set, update } = writable<QueryState>({
    query: '',
    isLoading: false,
    error: null,
    response: null,
    hasSubmitted: false,
  });

  return {
    subscribe,
    setQuery: (query: string) => update((state) => ({ ...state, query })),
    
    async execute(query: string, filters?: QueryRequest['filters']) {
      update((state) => ({
        ...state,
        query,
        isLoading: true,
        error: null,
        hasSubmitted: true,
      }));

      try {
        const response = await api.query({ query, filters });
        update((state) => ({
          ...state,
          isLoading: false,
          response,
        }));
        return response;
      } catch (err) {
        const error = err instanceof Error ? err.message : 'An error occurred';
        update((state) => ({
          ...state,
          isLoading: false,
          error,
        }));
        throw err;
      }
    },

    clear: () =>
      set({
        query: '',
        isLoading: false,
        error: null,
        response: null,
        hasSubmitted: false,
      }),
  };
}

export const queryStore = createQueryStore();

export const components = derived(queryStore, ($store) => {
  if (!$store.response) return [];
  return $store.response.components;
});

export const layout = derived(queryStore, ($store) => {
  return $store.response?.layout ?? null;
});

export const sources = derived(queryStore, ($store) => {
  return $store.response?.sources ?? [];
});

export const hasSubmitted = derived(queryStore, ($store) => $store.hasSubmitted);
