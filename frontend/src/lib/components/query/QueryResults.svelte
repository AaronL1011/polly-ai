<script lang="ts">
  import { queryStore, layout, components, sources } from '$lib/stores/query';
  import Dashboard from '$lib/components/layout/Dashboard.svelte';
</script>

{#if $queryStore.error}
  <div class="error">
    <p>{$queryStore.error}</p>
  </div>
{:else if $queryStore.isLoading}
  <div class="loading">
    <div class="loading-header">
      <div class="loading-icon">
        <div class="pulse-ring"></div>
        <div class="pulse-dot"></div>
      </div>
      <div class="loading-text">
        <p class="loading-title">Analysing your query</p>
        <p class="loading-subtitle">Searching documents and generating insights...</p>
      </div>
    </div>
    
    <div class="skeleton-grid">
      <div class="skeleton-card skeleton-card-large" style="animation-delay: 0ms;">
        <div class="skeleton-line skeleton-line-title"></div>
        <div class="skeleton-line skeleton-line-text"></div>
        <div class="skeleton-line skeleton-line-text skeleton-line-short"></div>
      </div>
      <div class="skeleton-card" style="animation-delay: 100ms;">
        <div class="skeleton-line skeleton-line-title"></div>
        <div class="skeleton-line skeleton-line-text"></div>
      </div>
      <div class="skeleton-card" style="animation-delay: 200ms;">
        <div class="skeleton-line skeleton-line-title"></div>
        <div class="skeleton-line skeleton-line-text"></div>
      </div>
    </div>
  </div>
{:else if $layout && $components.length > 0}
  <div class="results-container">
    <Dashboard layout={$layout} components={$components} sources={$sources} />
    
    {#if $queryStore.response}
      <div class="metadata">
        <span>Referenced {$queryStore.response.metadata.documents_retrieved} documents in {$queryStore.response.metadata.processing_time_ms / 1000}s</span>
        {#if $queryStore.response.cached}
          <span class="separator">·</span>
          <span class="cached">Cached</span>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .error {
    padding: var(--spacing-4);
    background: var(--color-error-light);
    border: 1px solid var(--color-error-muted);
    border-radius: var(--radius-md);
    color: var(--color-error-text);
    margin-top: var(--spacing-4);
  }

  .error p {
    margin: 0;
    font-size: var(--font-size-sm);
    line-height: var(--line-height-normal);
  }

  .loading {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-8);
    padding: var(--spacing-8) 0;
    animation: fadeIn 0.3s ease-out;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .loading-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-4);
  }

  .loading-icon {
    position: relative;
    width: 3rem;
    height: 3rem;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .pulse-ring {
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: var(--radius-full);
    background: var(--color-primary-muted);
    animation: pulseRing 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }

  .pulse-dot {
    position: relative;
    width: 1rem;
    height: 1rem;
    border-radius: var(--radius-full);
    background: var(--color-primary);
    animation: pulseDot 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }

  @keyframes pulseRing {
    0%, 100% {
      opacity: 0.4;
      transform: scale(0.8);
    }
    50% {
      opacity: 0.8;
      transform: scale(1);
    }
  }

  @keyframes pulseDot {
    0%, 100% {
      opacity: 0.8;
      transform: scale(0.9);
    }
    50% {
      opacity: 1;
      transform: scale(1);
    }
  }

  .loading-text {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .loading-title {
    margin: 0;
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-primary);
  }

  .loading-subtitle {
    margin: 0;
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .skeleton-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--spacing-4);
  }

  @media (min-width: 640px) {
    .skeleton-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .skeleton-card-large {
      grid-column: span 2;
    }
  }

  .skeleton-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--spacing-6);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
    animation: skeletonFadeIn 0.4s ease-out both;
  }

  @keyframes skeletonFadeIn {
    from {
      opacity: 0;
      transform: translateY(0.5rem);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .skeleton-line {
    background: linear-gradient(
      90deg,
      var(--color-gray-100) 0%,
      var(--color-gray-200) 50%,
      var(--color-gray-100) 100%
    );
    background-size: 200% 100%;
    border-radius: var(--radius-sm);
    animation: shimmer 1.5s ease-in-out infinite;
  }

  .skeleton-line-title {
    height: 1.25rem;
    width: 60%;
  }

  .skeleton-line-text {
    height: 0.875rem;
    width: 100%;
  }

  .skeleton-line-short {
    width: 75%;
  }

  @keyframes shimmer {
    0% {
      background-position: 200% 0;
    }
    100% {
      background-position: -200% 0;
    }
  }

  .results-container {
    animation: fadeSlideUp 0.5s ease-out;
  }

  @keyframes fadeSlideUp {
    from {
      opacity: 0;
      transform: translateY(1rem);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .metadata {
    display: flex;
    gap: var(--spacing-2);
    justify-content: center;
    align-items: center;
    margin-top: var(--spacing-6);
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
    animation: fadeIn 0.3s ease-out 0.3s both;
  }

  .separator {
    color: var(--color-text-muted);
  }

  .cached {
    color: var(--color-success);
    font-weight: var(--font-weight-medium);
  }
</style>
