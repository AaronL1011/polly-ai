<script lang="ts">
  import './styles/theme.css';
  import QueryInput from '$lib/components/query/QueryInput.svelte';
  import QueryResults from '$lib/components/query/QueryResults.svelte';
  import UploadPage from '$lib/components/upload/UploadPage.svelte';
  import { hasSubmitted } from '$lib/stores/query';

  let currentPath = $state(window.location.pathname);

  $effect(() => {
    const handlePopState = () => {
      currentPath = window.location.pathname;
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  });
</script>

{#if currentPath === '/upload'}
  <UploadPage />
{:else}
<main class:has-results={$hasSubmitted}>
  <div class="hero-section" class:collapsed={$hasSubmitted}>
    <div class="hero-content">
      <h1>Demócrata</h1>
      <p class="tagline">
        Democratising politics through clear, factual and intelligent data analysis.
      </p>
    </div>
    
    <div class="query-container">
      <QueryInput />
    </div>
  </div>

  {#if $hasSubmitted}
    <section class="results-section">
      <QueryResults />
    </section>

    <footer>
      <p>Demócrata strives to be non-partisan and factualy accurate. AI may have inaccuracies, always interrogate sources.</p>
    </footer>
  {/if}
</main>
{/if}

<style>
  main {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* Hero Section - Initial centered state */
  .hero-section {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    padding: var(--spacing-8);
    background: var(--color-surface);
    transition: min-height 0.5s cubic-bezier(0.4, 0, 0.2, 1),
                padding 0.5s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .hero-section.collapsed {
    min-height: auto;
    padding: var(--spacing-6) var(--spacing-8);
    border-bottom: 1px solid var(--color-border);
    box-shadow: var(--shadow-xs);
  }

  .hero-content {
    text-align: center;
    margin-bottom: var(--spacing-10);
    transition: margin-bottom 0.5s cubic-bezier(0.4, 0, 0.2, 1),
                opacity 0.3s ease;
  }

  .hero-section.collapsed .hero-content {
    margin-bottom: var(--spacing-4);
  }

  .hero-content h1 {
    font-family: 'Literata', serif;
    font-size: var(--font-size-4xl);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-heading);
    margin: 0 0 var(--spacing-3);
    letter-spacing: -0.025em;
    transition: font-size 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    animation: fadeSlideIn 0.4s ease-in-out;
  }

  .hero-section.collapsed .hero-content h1 {
    font-size: var(--font-size-2xl);
    margin-bottom: var(--spacing-1);
  }

  .tagline {
    color: var(--color-text-secondary);
    font-size: var(--font-size-lg);
    margin: 0;
    max-width: 48rem;
    line-height: var(--line-height-relaxed);
    transition: font-size 0.5s cubic-bezier(0.4, 0, 0.2, 1),
                opacity 0.3s ease;
    animation: fadeSlideIn 0.4s ease-in-out;

  }

  .hero-section.collapsed .tagline {
    font-size: var(--font-size-base);
  }

  .query-container {
    width: 100%;
    max-width: var(--max-width-md);
    transition: max-width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    animation: fadeSlideIn 0.6s ease-in-out;
  }

  .hero-section.collapsed .query-container {
    max-width: var(--max-width-lg);
  }

  /* Results Section */
  .results-section {
    flex: 1;
    padding: var(--spacing-8);
    max-width: var(--max-width-lg);
    width: 100%;
    margin: 0 auto;
    animation: fadeSlideIn 0.4s ease-out;
  }

  @keyframes fadeSlideIn {
    from {
      opacity: 0;
      transform: translateY(1rem);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  footer {
    padding: var(--spacing-6);
    text-align: center;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    border-top: 1px solid var(--color-border);
    background: var(--color-surface);
    animation: fadeIn 0.4s ease-out 0.2s both;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  footer p {
    margin: 0;
  }
</style>
