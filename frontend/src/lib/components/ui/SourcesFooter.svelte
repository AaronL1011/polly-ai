<script lang="ts">
  import type { SourceReference } from '$lib/api/client';

  interface Props {
    sources: SourceReference[];
  }

  let { sources }: Props = $props();

  function formatDate(dateStr: string | undefined): string {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-AU', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  }
</script>

{#if sources.length > 0}
  <footer class="sources-footer">
    <h3 class="sources-heading">Sources</h3>
    <ul class="sources-list">
      {#each sources as source (source.document_id)}
        <li class="source-item">
          {#if source.source_url}
            <a href={source.source_url} target="_blank" rel="noopener noreferrer" class="source-link">
              {source.source_name}
            </a>
          {:else}
            <span class="source-name">{source.source_name}</span>
          {/if}
          {#if source.source_date}
            <span class="source-date">{formatDate(source.source_date)}</span>
          {/if}
        </li>
      {/each}
    </ul>
  </footer>
{/if}

<style>
  .sources-footer {
    margin-top: var(--spacing-6);
    padding: var(--spacing-4) var(--spacing-5);
    background: var(--color-gray-50);
    border: 1px solid var(--color-border-light);
    border-radius: var(--radius-md);
  }

  .sources-heading {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 var(--spacing-3);
  }

  .sources-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .source-item {
    display: flex;
    align-items: baseline;
    gap: var(--spacing-2);
    font-size: var(--font-size-sm);
  }

  .source-link {
    color: var(--color-primary);
    text-decoration: none;
    transition: color var(--transition-fast);
  }

  .source-link:hover {
    color: var(--color-primary-hover);
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .source-name {
    color: var(--color-text-primary);
  }

  .source-date {
    color: var(--color-text-secondary);
    font-size: var(--font-size-xs);
  }

  .source-date::before {
    content: '·';
    margin-right: var(--spacing-2);
  }
</style>
