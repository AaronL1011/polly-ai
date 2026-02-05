<script lang="ts">
  import { authStore } from '$lib/stores/auth';

  interface Props {
    mode: 'login' | 'signup';
    onClose: () => void;
  }

  let { mode = $bindable(), onClose }: Props = $props();

  let email = $state('');
  let password = $state('');
  let confirmPassword = $state('');
  let error = $state<string | null>(null);
  let loading = $state(false);
  let successMessage = $state<string | null>(null);

  function toggleMode() {
    mode = mode === 'login' ? 'signup' : 'login';
    error = null;
    successMessage = null;
  }

  async function handleSubmit(event: Event) {
    event.preventDefault();
    error = null;
    successMessage = null;

    if (!email || !password) {
      error = 'Please fill in all fields';
      return;
    }

    if (mode === 'signup' && password !== confirmPassword) {
      error = 'Passwords do not match';
      return;
    }

    if (password.length < 6) {
      error = 'Password must be at least 6 characters';
      return;
    }

    loading = true;

    try {
      if (mode === 'login') {
        const result = await authStore.signIn(email, password);
        if (result.error) {
          error = result.error;
        } else {
          onClose();
        }
      } else {
        const result = await authStore.signUp(email, password);
        if (result.error) {
          error = result.error;
        } else {
          successMessage = 'Check your email to confirm your account';
        }
      }
    } finally {
      loading = false;
    }
  }

  function handleBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) {
      onClose();
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      onClose();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="modal-backdrop" onclick={handleBackdropClick} role="dialog" aria-modal="true" tabindex="-1">
  <div class="modal">
    <button class="close-button" onclick={onClose} aria-label="Close">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
      </svg>
    </button>

    <div class="modal-header">
      <h2>{mode === 'login' ? 'Sign In' : 'Create Account'}</h2>
      <p class="subtitle">
        {mode === 'login'
          ? 'Welcome back to Demócrata'
          : 'Start exploring political data'}
      </p>
    </div>

    {#if error}
      <div class="error-message">{error}</div>
    {/if}

    {#if successMessage}
      <div class="success-message">{successMessage}</div>
    {:else}
      <form onsubmit={handleSubmit}>
        <div class="form-field">
          <label for="email">Email</label>
          <input
            id="email"
            type="email"
            bind:value={email}
            placeholder="you@example.com"
            autocomplete="email"
            disabled={loading}
          />
        </div>

        <div class="form-field">
          <label for="password">Password</label>
          <input
            id="password"
            type="password"
            bind:value={password}
            placeholder="••••••••"
            autocomplete={mode === 'login' ? 'current-password' : 'new-password'}
            disabled={loading}
          />
        </div>

        {#if mode === 'signup'}
          <div class="form-field">
            <label for="confirm-password">Confirm Password</label>
            <input
              id="confirm-password"
              type="password"
              bind:value={confirmPassword}
              placeholder="••••••••"
              autocomplete="new-password"
              disabled={loading}
            />
          </div>
        {/if}

        <button type="submit" class="submit-button" disabled={loading}>
          {#if loading}
            <span class="spinner"></span>
          {:else}
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          {/if}
        </button>
      </form>

      <div class="toggle-mode">
        {#if mode === 'login'}
          Don't have an account?
          <button type="button" onclick={toggleMode}>Sign up</button>
        {:else}
          Already have an account?
          <button type="button" onclick={toggleMode}>Sign in</button>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    padding: var(--spacing-4);
    animation: fadeIn 0.15s ease-out;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .modal {
    background: var(--color-surface);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-xl);
    width: 100%;
    max-width: 400px;
    padding: var(--spacing-6);
    position: relative;
    animation: slideIn 0.2s ease-out;
  }

  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateY(-20px) scale(0.95);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  .close-button {
    position: absolute;
    top: var(--spacing-4);
    right: var(--spacing-4);
    width: 32px;
    height: 32px;
    border: none;
    background: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    color: var(--color-text-muted);
    transition: color var(--transition-fast), background var(--transition-fast);
  }

  .close-button:hover {
    color: var(--color-text-primary);
    background: var(--color-surface-hover);
  }

  .close-button svg {
    width: 20px;
    height: 20px;
  }

  .modal-header {
    text-align: center;
    margin-bottom: var(--spacing-6);
  }

  .modal-header h2 {
    font-family: 'Literata', serif;
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-heading);
    margin: 0 0 var(--spacing-2);
  }

  .subtitle {
    color: var(--color-text-secondary);
    font-size: var(--font-size-sm);
    margin: 0;
  }

  .error-message {
    background: var(--color-error-light);
    color: var(--color-error-text);
    padding: var(--spacing-3);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    margin-bottom: var(--spacing-4);
    text-align: center;
  }

  .success-message {
    background: var(--color-success-light);
    color: var(--color-success-text);
    padding: var(--spacing-4);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    text-align: center;
  }

  form {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
  }

  .form-field {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .form-field label {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-primary);
  }

  .form-field input {
    padding: var(--spacing-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    background: var(--color-surface);
    color: var(--color-text-primary);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }

  .form-field input:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary-muted);
  }

  .form-field input::placeholder {
    color: var(--color-text-muted);
  }

  .form-field input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .submit-button {
    padding: var(--spacing-3);
    background: var(--color-primary);
    color: var(--color-text-inverse);
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: background var(--transition-fast);
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 44px;
  }

  .submit-button:hover:not(:disabled) {
    background: var(--color-primary-hover);
  }

  .submit-button:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .toggle-mode {
    text-align: center;
    margin-top: var(--spacing-4);
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .toggle-mode button {
    background: none;
    border: none;
    color: var(--color-primary);
    cursor: pointer;
    font-weight: var(--font-weight-medium);
    padding: 0;
    margin-left: var(--spacing-1);
  }

  .toggle-mode button:hover {
    text-decoration: underline;
  }
</style>
