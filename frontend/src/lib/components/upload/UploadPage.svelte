<script lang="ts">
  import { api } from '$lib/api/client';

  let selectedFile: File | null = $state(null);
  let title = $state('');
  let sourceUrl = $state('');
  let documentType = $state('other');
  let uploading = $state(false);
  let result: { success: boolean; message: string; jobId?: string } | null = $state(null);

  function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      selectedFile = input.files[0];
      if (!title) {
        title = selectedFile.name.replace(/\.[^/.]+$/, '');
      }
    }
  }

  async function handleUpload() {
    if (!selectedFile) return;

    uploading = true;
    result = null;

    try {
      const response = await api.upload(selectedFile, {
        title: title || selectedFile.name,
        document_type: documentType,
        source: 'manual',
        source_url: sourceUrl || undefined,
      });

      result = {
        success: true,
        message: `Upload successful! Job ID: ${response.job_id}`,
        jobId: response.job_id,
      };
      
      selectedFile = null;
      title = '';
      sourceUrl = '';
    } catch (error) {
      result = {
        success: false,
        message: error instanceof Error ? error.message : 'Upload failed',
      };
    } finally {
      uploading = false;
    }
  }
</script>

<main>
  <header>
    <h1>Upload Document</h1>
    <p class="tagline">Upload PDF or text files for ingestion</p>
  </header>

  <section class="upload-section">
    <form onsubmit={(e) => { e.preventDefault(); handleUpload(); }}>
      <div class="form-group">
        <label for="file">Select File</label>
        <input
          type="file"
          id="file"
          accept=".pdf,.txt,.md,.json,.csv"
          onchange={handleFileSelect}
          disabled={uploading}
        />
        {#if selectedFile}
          <p class="file-info">Selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)</p>
        {/if}
      </div>

      <div class="form-group">
        <label for="title">Document Title</label>
        <input
          type="text"
          id="title"
          bind:value={title}
          placeholder="Enter document title"
          disabled={uploading}
        />
      </div>

      <div class="form-group">
        <label for="sourceUrl">Source URL</label>
        <input
          type="url"
          id="sourceUrl"
          bind:value={sourceUrl}
          placeholder="https://example.com/document"
          disabled={uploading}
        />
        <p class="field-hint">Optional: URL where this document was sourced from</p>
      </div>

      <div class="form-group">
        <label for="docType">Document Type</label>
        <select id="docType" bind:value={documentType} disabled={uploading}>
          <option value="other">Other</option>
          <option value="bill">Bill</option>
          <option value="hansard">Hansard</option>
          <option value="report">Report</option>
          <option value="vote">Vote</option>
          <option value="member">Member</option>
        </select>
      </div>

      <button type="submit" disabled={!selectedFile || uploading}>
        {uploading ? 'Uploading...' : 'Upload'}
      </button>
    </form>

    {#if result}
      <div class="result" class:success={result.success} class:error={!result.success}>
        {result.message}
      </div>
    {/if}
  </section>

  <footer>
    <a href="/">Back to Query</a>
  </footer>
</main>

<style>
  main {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  header {
    padding: var(--spacing-8);
    text-align: center;
    background: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
    box-shadow: var(--shadow-xs);
  }

  header h1 {
    font-size: var(--font-size-3xl);
    font-weight: var(--font-weight-bold);
    color: var(--color-text-heading);
    margin: 0 0 var(--spacing-2);
    letter-spacing: -0.025em;
  }

  .tagline {
    color: var(--color-text-secondary);
    font-size: var(--font-size-base);
    margin: 0;
  }

  .upload-section {
    flex: 1;
    padding: var(--spacing-8);
    max-width: var(--max-width-sm);
    width: 100%;
    margin: 0 auto;
  }

  form {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-6);
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  label {
    font-weight: var(--font-weight-medium);
    color: var(--color-gray-700);
    font-size: var(--font-size-sm);
  }

  input[type="text"],
  input[type="url"],
  select {
    padding: var(--spacing-3);
    border: 1px solid var(--color-gray-300);
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    font-family: inherit;
    color: var(--color-text-primary);
    background: var(--color-surface);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }

  input[type="text"]:focus,
  input[type="url"]:focus,
  select:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: var(--focus-ring);
  }

  input[type="text"]:disabled,
  input[type="url"]:disabled,
  select:disabled {
    background: var(--color-gray-50);
    color: var(--color-text-secondary);
    cursor: not-allowed;
  }

  input[type="file"] {
    padding: var(--spacing-4);
    border: 2px dashed var(--color-gray-300);
    border-radius: var(--radius-md);
    background: var(--color-gray-50);
    cursor: pointer;
    font-family: inherit;
    color: var(--color-text-secondary);
    transition: border-color var(--transition-fast), background-color var(--transition-fast);
  }

  input[type="file"]:hover:not(:disabled) {
    border-color: var(--color-primary);
    background: var(--color-primary-light);
  }

  input[type="file"]:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .file-info {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
    margin: 0;
  }

  .field-hint {
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
    margin: 0;
  }

  button {
    padding: var(--spacing-3) var(--spacing-6);
    background: var(--color-primary);
    color: var(--color-text-inverse);
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-medium);
    font-family: inherit;
    cursor: pointer;
    transition: background-color var(--transition-fast), transform var(--transition-fast);
  }

  button:hover:not(:disabled) {
    background: var(--color-primary-hover);
  }

  button:active:not(:disabled) {
    background: var(--color-primary-active);
    transform: translateY(1px);
  }

  button:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
  }

  button:disabled {
    background: var(--color-gray-300);
    cursor: not-allowed;
  }

  .result {
    margin-top: var(--spacing-4);
    padding: var(--spacing-4);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
  }

  .result.success {
    background: var(--color-success-light);
    color: var(--color-success-text);
    border: 1px solid var(--color-success-muted);
  }

  .result.error {
    background: var(--color-error-light);
    color: var(--color-error-text);
    border: 1px solid var(--color-error-muted);
  }

  footer {
    padding: var(--spacing-6);
    text-align: center;
    border-top: 1px solid var(--color-border);
    background: var(--color-surface);
  }

  footer a {
    color: var(--color-primary);
    text-decoration: none;
    font-weight: var(--font-weight-medium);
    transition: color var(--transition-fast);
  }

  footer a:hover {
    color: var(--color-primary-hover);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
</style>
