<script lang="ts">
  import type { LayoutData, ComponentData, SourceReference } from '$lib/api/client';
  import Section from './Section.svelte';
  import SourcesFooter from '$lib/components/ui/SourcesFooter.svelte';

  interface Props {
    layout: LayoutData;
    components: ComponentData[];
    sources?: SourceReference[];
  }

  let { layout, components, sources = [] }: Props = $props();

  function getComponentsForSection(componentIds: string[]): ComponentData[] {
    return componentIds
      .map((id) => components.find((c) => c.id === id))
      .filter((c): c is ComponentData => c !== undefined);
  }

</script>

<div class="dashboard">
  {#if layout.title}
    <header class="dashboard-header">
      <h1 class="title">{layout.title}</h1>
      {#if layout.subtitle}
        <p class="subtitle">{layout.subtitle}</p>
      {/if}
    </header>
  {/if}

  <div class="sections">
    {#each layout.sections as section}
      <Section
        title={section.title}
        components={getComponentsForSection(section.component_ids)}
        layout={section.layout}
      />
    {/each}
  </div>

  <SourcesFooter {sources} />
</div>

<style>
  .dashboard {
    margin-top: var(--spacing-6);
  }

  .dashboard-header {
    margin-bottom: var(--spacing-6);
  }

  .title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-heading);
    margin: 0;
    letter-spacing: var(--letter-spacing-tight);
  }

  .subtitle {
    font-size: var(--font-size-base);
    color: var(--color-text-secondary);
    margin: var(--spacing-2) 0 0;
    line-height: var(--line-height-relaxed);
    max-width: 48rem;
  }

  .sections {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-5);
  }
</style>
