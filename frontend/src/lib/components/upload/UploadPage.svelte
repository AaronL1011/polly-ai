<script lang="ts">
  import { api } from '$lib/api/client';

  type UploadStatus = 'pending' | 'uploading' | 'success' | 'error';
  type DocumentType = 'other' | 'bill' | 'hansard' | 'report' | 'vote' | 'member';

  interface QueuedFile {
    id: string;
    file: File;
    title: string;
    documentType: DocumentType;
    sourceUrl: string;
    status: UploadStatus;
    progress: number;
    jobId?: string;
    errorMessage?: string;
  }

  const DOCUMENT_TYPES: { value: DocumentType; label: string }[] = [
    { value: 'other', label: 'Other' },
    { value: 'bill', label: 'Bill' },
    { value: 'hansard', label: 'Hansard' },
    { value: 'report', label: 'Report' },
    { value: 'vote', label: 'Vote' },
    { value: 'member', label: 'Member' },
  ];

  let fileQueue: QueuedFile[] = $state([]);
  let isUploading = $state(false);
  let currentUploadIndex = $state(-1);
  let dragOver = $state(false);
  let expandedFileId: string | null = $state(null);

  const completedCount = $derived(fileQueue.filter(f => f.status === 'success').length);
  const failedCount = $derived(fileQueue.filter(f => f.status === 'error').length);
  const pendingCount = $derived(fileQueue.filter(f => f.status === 'pending').length);
  const totalCount = $derived(fileQueue.length);
  const overallProgress = $derived(
    totalCount > 0 ? Math.round(((completedCount + failedCount) / totalCount) * 100) : 0
  );
  const hasFilesInQueue = $derived(fileQueue.length > 0);
  const canStartUpload = $derived(hasFilesInQueue && !isUploading && pendingCount > 0);

  function generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      addFilesToQueue(Array.from(input.files));
      input.value = '';
    }
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    dragOver = false;
    
    if (event.dataTransfer?.files) {
      const validFiles = Array.from(event.dataTransfer.files).filter(file => 
        /\.(pdf|txt|md|json|csv)$/i.test(file.name)
      );
      if (validFiles.length > 0) {
        addFilesToQueue(validFiles);
      }
    }
  }

  function handleDragOver(event: DragEvent) {
    event.preventDefault();
    dragOver = true;
  }

  function handleDragLeave() {
    dragOver = false;
  }

  function addFilesToQueue(files: File[]) {
    const newQueuedFiles: QueuedFile[] = files.map(file => ({
      id: generateId(),
      file,
      title: file.name.replace(/\.[^/.]+$/, ''),
      documentType: 'other',
      sourceUrl: '',
      status: 'pending',
      progress: 0,
    }));
    fileQueue = [...fileQueue, ...newQueuedFiles];
    
    // Auto-expand first file if it's the only one added
    if (newQueuedFiles.length === 1 && fileQueue.length === 1) {
      expandedFileId = newQueuedFiles[0].id;
    }
  }

  function removeFromQueue(id: string) {
    if (isUploading) return;
    fileQueue = fileQueue.filter(f => f.id !== id);
    if (expandedFileId === id) {
      expandedFileId = null;
    }
  }

  function updateFile(id: string, updates: Partial<Pick<QueuedFile, 'title' | 'documentType' | 'sourceUrl'>>) {
    fileQueue = fileQueue.map(f => 
      f.id === id ? { ...f, ...updates } : f
    );
  }

  function toggleExpanded(id: string) {
    expandedFileId = expandedFileId === id ? null : id;
  }

  function clearCompleted() {
    fileQueue = fileQueue.filter(f => f.status !== 'success');
  }

  function clearAll() {
    if (isUploading) return;
    fileQueue = [];
    expandedFileId = null;
  }

  async function uploadFile(queuedFile: QueuedFile): Promise<void> {
    fileQueue = fileQueue.map(f => 
      f.id === queuedFile.id ? { ...f, status: 'uploading', progress: 0 } : f
    );

    try {
      const response = await api.upload(queuedFile.file, {
        title: queuedFile.title || queuedFile.file.name,
        document_type: queuedFile.documentType,
        source: 'manual',
        source_url: queuedFile.sourceUrl || undefined,
      });

      fileQueue = fileQueue.map(f => 
        f.id === queuedFile.id 
          ? { ...f, status: 'success', progress: 100, jobId: response.job_id }
          : f
      );
    } catch (error) {
      fileQueue = fileQueue.map(f => 
        f.id === queuedFile.id 
          ? { 
              ...f, 
              status: 'error', 
              progress: 0,
              errorMessage: error instanceof Error ? error.message : 'Upload failed'
            }
          : f
      );
    }
  }

  async function startUpload() {
    if (!canStartUpload) return;

    isUploading = true;
    expandedFileId = null;
    const pendingFiles = fileQueue.filter(f => f.status === 'pending');

    for (let i = 0; i < pendingFiles.length; i++) {
      currentUploadIndex = i;
      await uploadFile(pendingFiles[i]);
    }

    currentUploadIndex = -1;
    isUploading = false;
  }

  function retryFailed() {
    fileQueue = fileQueue.map(f => 
      f.status === 'error' 
        ? { ...f, status: 'pending', progress: 0, errorMessage: undefined }
        : f
    );
  }

  function navigateHome() {
    window.history.pushState({}, '', '/');
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
</script>

<div class="upload-page">
  <header class="upload-header">
    <button class="back-link" onclick={navigateHome}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="15 18 9 12 15 6" />
      </svg>
      Back to Home
    </button>
    <h1>Upload Documents</h1>
    <p class="tagline">Upload PDF or text files for ingestion</p>
  </header>

  <section class="upload-section">
    <!-- Drop Zone -->
    <div
      class="drop-zone"
      class:drag-over={dragOver}
      class:disabled={isUploading}
      ondrop={handleDrop}
      ondragover={handleDragOver}
      ondragleave={handleDragLeave}
      role="button"
      tabindex="0"
    >
      <div class="drop-zone-content">
        <svg class="drop-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M12 16V4m0 0L8 8m4-4l4 4" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M3 16v2a2 2 0 002 2h14a2 2 0 002-2v-2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <p class="drop-text">Drop files here or click to select</p>
        <p class="drop-hint">PDF, TXT, MD, JSON, CSV</p>
      </div>
      <input
        type="file"
        accept=".pdf,.txt,.md,.json,.csv"
        onchange={handleFileSelect}
        disabled={isUploading}
        multiple
        class="file-input-hidden"
      />
    </div>

    <!-- Upload Queue -->
    {#if hasFilesInQueue}
      <div class="queue-section">
        <div class="queue-header">
          <h3 class="queue-title">
            Upload Queue
            <span class="queue-count">{totalCount} file{totalCount !== 1 ? 's' : ''}</span>
          </h3>
          {#if !isUploading}
            <button type="button" class="text-button" onclick={clearAll}>Clear all</button>
          {/if}
        </div>

        <!-- Overall Progress -->
        {#if isUploading || completedCount > 0 || failedCount > 0}
          <div class="overall-progress">
            <div class="progress-stats">
              <span class="progress-label">
                {#if isUploading}
                  Uploading {completedCount + 1} of {totalCount}...
                {:else if pendingCount > 0}
                  {completedCount} of {totalCount} completed
                {:else}
                  Upload complete
                {/if}
              </span>
              <span class="progress-percent">{overallProgress}%</span>
            </div>
            <div class="progress-bar-track">
              <div class="progress-bar-fill" style="width: {overallProgress}%"></div>
            </div>
            <div class="progress-summary">
              {#if completedCount > 0}
                <span class="summary-success">{completedCount} succeeded</span>
              {/if}
              {#if failedCount > 0}
                <span class="summary-error">{failedCount} failed</span>
              {/if}
              {#if pendingCount > 0 && !isUploading}
                <span class="summary-pending">{pendingCount} pending</span>
              {/if}
            </div>
          </div>
        {/if}

        <!-- File List -->
        <ul class="file-list">
          {#each fileQueue as queuedFile (queuedFile.id)}
            {@const isExpanded = expandedFileId === queuedFile.id}
            {@const canEdit = queuedFile.status === 'pending' && !isUploading}
            <li class="file-item" class:uploading={queuedFile.status === 'uploading'} class:expanded={isExpanded}>
              <div class="file-item-header">
                <div class="file-item-main">
                  <div class="file-icon-wrapper" class:success={queuedFile.status === 'success'} class:error={queuedFile.status === 'error'} class:uploading={queuedFile.status === 'uploading'}>
                    {#if queuedFile.status === 'success'}
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                    {:else if queuedFile.status === 'error'}
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                    {:else if queuedFile.status === 'uploading'}
                      <div class="spinner"></div>
                    {:else}
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                    {/if}
                  </div>
                  <div class="file-details">
                    <div class="file-title-row">
                      <span class="file-title">{queuedFile.title || queuedFile.file.name}</span>
                      {#if queuedFile.documentType !== 'other'}
                        <span class="file-type-badge">{DOCUMENT_TYPES.find(t => t.value === queuedFile.documentType)?.label}</span>
                      {/if}
                    </div>
                    <div class="file-meta">
                      <span class="file-name">{queuedFile.file.name}</span>
                      <span class="file-size">{formatFileSize(queuedFile.file.size)}</span>
                    </div>
                    {#if queuedFile.status === 'error' && queuedFile.errorMessage}
                      <p class="file-error">{queuedFile.errorMessage}</p>
                    {/if}
                    {#if queuedFile.status === 'success' && queuedFile.jobId}
                      <p class="file-success">Job ID: {queuedFile.jobId}</p>
                    {/if}
                  </div>
                </div>
                <div class="file-actions">
                  {#if canEdit}
                    <button
                      type="button"
                      class="expand-button"
                      class:expanded={isExpanded}
                      onclick={() => toggleExpanded(queuedFile.id)}
                      aria-label={isExpanded ? 'Collapse details' : 'Expand details'}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M19 9l-7 7-7-7" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                    </button>
                    <button
                      type="button"
                      class="remove-button"
                      onclick={() => removeFromQueue(queuedFile.id)}
                      aria-label="Remove file"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                    </button>
                  {/if}
                </div>
              </div>
              
              {#if isExpanded && canEdit}
                <div class="file-item-expanded">
                  <div class="expanded-form">
                    <div class="form-group">
                      <label for="title-{queuedFile.id}">Title</label>
                      <input
                        type="text"
                        id="title-{queuedFile.id}"
                        value={queuedFile.title}
                        oninput={(e) => updateFile(queuedFile.id, { title: (e.target as HTMLInputElement).value })}
                        placeholder="Document title"
                      />
                    </div>
                    <div class="form-row">
                      <div class="form-group">
                        <label for="type-{queuedFile.id}">Document Type</label>
                        <select
                          id="type-{queuedFile.id}"
                          value={queuedFile.documentType}
                          onchange={(e) => updateFile(queuedFile.id, { documentType: (e.target as HTMLSelectElement).value as DocumentType })}
                        >
                          {#each DOCUMENT_TYPES as docType}
                            <option value={docType.value}>{docType.label}</option>
                          {/each}
                        </select>
                      </div>
                      <div class="form-group">
                        <label for="url-{queuedFile.id}">Source URL</label>
                        <input
                          type="url"
                          id="url-{queuedFile.id}"
                          value={queuedFile.sourceUrl}
                          oninput={(e) => updateFile(queuedFile.id, { sourceUrl: (e.target as HTMLInputElement).value })}
                          placeholder="https://example.com"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              {/if}
            </li>
          {/each}
        </ul>

        <!-- Action Buttons -->
        <div class="queue-actions">
          {#if failedCount > 0 && !isUploading}
            <button type="button" class="secondary-button" onclick={retryFailed}>
              Retry failed ({failedCount})
            </button>
          {/if}
          {#if completedCount > 0 && !isUploading}
            <button type="button" class="secondary-button" onclick={clearCompleted}>
              Clear completed
            </button>
          {/if}
          <button
            type="button"
            class="primary-button"
            onclick={startUpload}
            disabled={!canStartUpload}
          >
            {#if isUploading}
              <span class="button-spinner"></span>
              Uploading...
            {:else}
              Upload {pendingCount} file{pendingCount !== 1 ? 's' : ''}
            {/if}
          </button>
        </div>
      </div>
    {/if}
  </section>
</div>

<style>
  .upload-page {
    min-height: 100vh;
    background: var(--color-background);
    padding: var(--spacing-6);
  }

  .upload-header {
    max-width: var(--max-width-md);
    margin: 0 auto var(--spacing-6);
  }

  .back-link {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-1);
    background: none;
    border: none;
    color: var(--color-text-secondary);
    font-size: var(--font-size-sm);
    cursor: pointer;
    padding: 0;
    margin-bottom: var(--spacing-4);
    transition: color var(--transition-fast);
  }

  .back-link:hover {
    color: var(--color-primary);
  }

  .back-link svg {
    width: 16px;
    height: 16px;
  }

  .upload-header h1 {
    font-family: 'Literata', serif;
    font-size: var(--font-size-3xl);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-heading);
    margin: 0 0 var(--spacing-8);
  }

  .tagline {
    color: var(--color-text-secondary);
    font-size: var(--font-size-base);
    margin: 0;
  }

  .upload-section {
    max-width: var(--max-width-md);
    width: 100%;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-6);
  }

  /* Drop Zone */
  .drop-zone {
    position: relative;
    padding: var(--spacing-10);
    border: 2px dashed var(--color-gray-300);
    border-radius: var(--radius-lg);
    background: var(--color-gray-50);
    cursor: pointer;
    transition: border-color var(--transition-base), background-color var(--transition-base);
  }

  .drop-zone:hover:not(.disabled),
  .drop-zone.drag-over {
    border-color: var(--color-primary);
    background: var(--color-primary-light);
  }

  .drop-zone.disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .drop-zone-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-2);
    pointer-events: none;
  }

  .drop-icon {
    width: 2.5rem;
    height: 2.5rem;
    color: var(--color-gray-400);
    transition: color var(--transition-base);
  }

  .drop-zone:hover:not(.disabled) .drop-icon,
  .drop-zone.drag-over .drop-icon {
    color: var(--color-primary);
  }

  .drop-text {
    margin: 0;
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-secondary);
  }

  .drop-hint {
    margin: 0;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .file-input-hidden {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }

  .file-input-hidden:disabled {
    cursor: not-allowed;
  }

  /* Queue Section */
  .queue-section {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
  }

  .queue-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .queue-title {
    margin: 0;
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-heading);
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
  }

  .queue-count {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-normal);
    color: var(--color-text-muted);
  }

  .text-button {
    padding: var(--spacing-1) var(--spacing-2);
    background: transparent;
    border: none;
    color: var(--color-text-secondary);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: color var(--transition-fast);
  }

  .text-button:hover {
    color: var(--color-primary);
  }

  /* Overall Progress */
  .overall-progress {
    padding: var(--spacing-4);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .progress-stats {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-2);
  }

  .progress-label {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-primary);
  }

  .progress-percent {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    color: var(--color-primary);
    font-variant-numeric: tabular-nums;
  }

  .progress-bar-track {
    height: 6px;
    background: var(--color-gray-200);
    border-radius: var(--radius-full);
    overflow: hidden;
  }

  .progress-bar-fill {
    height: 100%;
    background: var(--color-primary);
    border-radius: var(--radius-full);
    transition: width var(--transition-base);
  }

  .progress-summary {
    display: flex;
    gap: var(--spacing-4);
    margin-top: var(--spacing-2);
    font-size: var(--font-size-xs);
  }

  .summary-success {
    color: var(--color-success-text);
  }

  .summary-error {
    color: var(--color-error-text);
  }

  .summary-pending {
    color: var(--color-text-muted);
  }

  /* File List */
  .file-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .file-item {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
    overflow: hidden;
  }

  .file-item.uploading {
    border-color: var(--color-primary-muted);
    box-shadow: 0 0 0 1px var(--color-primary-muted);
  }

  .file-item.expanded {
    border-color: var(--color-gray-300);
  }

  .file-item-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--spacing-3);
    padding: var(--spacing-4);
  }

  .file-item-main {
    display: flex;
    gap: var(--spacing-3);
    flex: 1;
    min-width: 0;
  }

  .file-icon-wrapper {
    flex-shrink: 0;
    width: 2.25rem;
    height: 2.25rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-gray-100);
    border-radius: var(--radius-md);
    color: var(--color-gray-500);
    transition: background-color var(--transition-fast), color var(--transition-fast);
  }

  .file-icon-wrapper svg {
    width: 1.25rem;
    height: 1.25rem;
  }

  .file-icon-wrapper.success {
    background: var(--color-success-light);
    color: var(--color-success);
  }

  .file-icon-wrapper.error {
    background: var(--color-error-light);
    color: var(--color-error);
  }

  .file-icon-wrapper.uploading {
    background: var(--color-primary-light);
    color: var(--color-primary);
  }

  .spinner {
    width: 1rem;
    height: 1rem;
    border: 2px solid var(--color-primary-muted);
    border-top-color: var(--color-primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .file-details {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .file-title-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    min-width: 0;
  }

  .file-title {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .file-type-badge {
    flex-shrink: 0;
    padding: var(--spacing-1) var(--spacing-2);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    color: var(--color-primary);
    background: var(--color-primary-light);
    border-radius: var(--radius-sm);
  }

  .file-meta {
    display: flex;
    gap: var(--spacing-3);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .file-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .file-size {
    flex-shrink: 0;
  }

  .file-error {
    margin: 0;
    font-size: var(--font-size-xs);
    color: var(--color-error-text);
  }

  .file-success {
    margin: 0;
    font-size: var(--font-size-xs);
    color: var(--color-success-text);
  }

  .file-actions {
    display: flex;
    gap: var(--spacing-1);
    flex-shrink: 0;
  }

  .expand-button,
  .remove-button {
    flex-shrink: 0;
    padding: var(--spacing-2);
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--color-gray-400);
    cursor: pointer;
    transition: color var(--transition-fast), background-color var(--transition-fast), transform var(--transition-fast);
  }

  .expand-button:hover {
    color: var(--color-primary);
    background: var(--color-primary-light);
  }

  .expand-button.expanded {
    transform: rotate(180deg);
  }

  .remove-button:hover {
    color: var(--color-error);
    background: var(--color-error-light);
  }

  .expand-button svg,
  .remove-button svg {
    width: 1rem;
    height: 1rem;
    display: block;
  }

  /* Expanded Form */
  .file-item-expanded {
    padding: 0 var(--spacing-4) var(--spacing-4);
    padding-left: calc(var(--spacing-4) + 2.25rem + var(--spacing-3));
  }

  .expanded-form {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
    padding: var(--spacing-4);
    background: var(--color-gray-50);
    border-radius: var(--radius-md);
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .form-group label {
    font-weight: var(--font-weight-medium);
    color: var(--color-text-secondary);
    font-size: var(--font-size-xs);
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-3);
  }

  @media (max-width: 600px) {
    .form-row {
      grid-template-columns: 1fr;
    }
  }

  .expanded-form input[type="text"],
  .expanded-form input[type="url"],
  .expanded-form select {
    padding: var(--spacing-2) var(--spacing-3);
    border: 1px solid var(--color-gray-300);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    font-family: inherit;
    color: var(--color-text-primary);
    background: var(--color-surface);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }

  .expanded-form input[type="text"]:focus,
  .expanded-form input[type="url"]:focus,
  .expanded-form select:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: var(--focus-ring);
  }

  /* Action Buttons */
  .queue-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--spacing-3);
    padding-top: var(--spacing-2);
  }

  .primary-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-2);
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

  .primary-button:hover:not(:disabled) {
    background: var(--color-primary-hover);
  }

  .primary-button:active:not(:disabled) {
    background: var(--color-primary-active);
    transform: translateY(1px);
  }

  .primary-button:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
  }

  .primary-button:disabled {
    background: var(--color-gray-300);
    cursor: not-allowed;
  }

  .secondary-button {
    padding: var(--spacing-3) var(--spacing-5);
    background: var(--color-surface);
    color: var(--color-text-primary);
    border: 1px solid var(--color-gray-300);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    font-family: inherit;
    cursor: pointer;
    transition: border-color var(--transition-fast), background-color var(--transition-fast);
  }

  .secondary-button:hover {
    border-color: var(--color-gray-400);
    background: var(--color-gray-50);
  }

  .button-spinner {
    width: 1rem;
    height: 1rem;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
</style>
