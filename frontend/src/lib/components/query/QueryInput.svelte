<script lang="ts">
  import { queryStore } from '$lib/stores/query';

  let query = $state('');

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (!query.trim() || $queryStore.isLoading) return;
    await queryStore.execute(query.trim());
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      handleSubmit(e);
    }
  }
</script>

<form onsubmit={handleSubmit} class="query-form">
  <div class="input-wrapper">
    <textarea
      bind:value={query}
      onkeydown={handleKeydown}
      placeholder="What would you like to know?"
      disabled={$queryStore.isLoading}
      rows="2"
    ></textarea>
    <button type="submit" disabled={!query.trim() || $queryStore.isLoading}>
      {$queryStore.isLoading ? 'Searching...' : 'Search'}
    </button>
  </div>
</form>

<style>
  .query-form {
    width: 100%;
    max-width: var(--max-width-md);
    margin: 0 auto;
  }

  .input-wrapper {
    display: flex;
    gap: var(--spacing-3);
    align-items: center;
  }

  textarea {
    flex: 1;
    padding: var(--spacing-3) var(--spacing-4);
    font-size: var(--font-size-lg);
    font-family: inherit;
    line-height: var(--line-height-normal);
    color: var(--color-text-primary);
    background: var(--color-surface);
    border: 1px solid var(--color-gray-300);
    border-radius: var(--radius-md);
    resize: none;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }

  textarea::placeholder {
    color: var(--color-text-muted);
    font-size: var(--font-size-lg);
  }

  textarea:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: var(--focus-ring);
  }

  textarea:disabled {
    background: var(--color-gray-50);
    color: var(--color-text-secondary);
    cursor: not-allowed;
  }

  button {
    padding: var(--spacing-3) var(--spacing-6);
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-bold);
    font-family: inherit;
    color: var(--color-primary);
    background: transparent;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    white-space: nowrap;
    transition: background-color var(--transition-fast), transform var(--transition-fast);
  }

  button:hover:not(:disabled) {
    background: var(--color-surface-hover);
  }

  button:active:not(:disabled) {
    /* background: var(--color-primary-active); */
    transform: translateY(1px);
  }

  button:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
  }

  button:disabled {
    color: var(--color-gray-300);
    cursor: not-allowed;
  }
</style>
