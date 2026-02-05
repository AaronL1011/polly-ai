<script lang="ts">
  import { authStore, isAuthenticated, currentUser, activeOrganization, currentContextName } from '$lib/stores/auth';
  import AuthModal from './AuthModal.svelte';

  let isOpen = $state(false);
  let showAuthModal = $state(false);
  let authModalMode = $state<'login' | 'signup'>('login');

  function toggleMenu() {
    isOpen = !isOpen;
  }

  function closeMenu() {
    isOpen = false;
  }

  function openAuthModal(mode: 'login' | 'signup') {
    authModalMode = mode;
    showAuthModal = true;
    closeMenu();
  }

  function closeAuthModal() {
    showAuthModal = false;
  }

  async function handleSignOut() {
    await authStore.signOut();
    closeMenu();
  }

  function switchToPersonal() {
    authStore.switchContext('personal');
    closeMenu();
  }

  function switchToOrg(orgId: string) {
    authStore.switchContext(orgId);
    closeMenu();
  }

  function navigateToSettings() {
    window.history.pushState({}, '', '/settings');
    window.dispatchEvent(new PopStateEvent('popstate'));
    closeMenu();
  }

  function navigateToUpload() {
    window.history.pushState({}, '', '/upload');
    window.dispatchEvent(new PopStateEvent('popstate'));
    closeMenu();
  }

  // Close menu when clicking outside
  function handleClickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.user-menu')) {
      closeMenu();
    }
  }

  // Get user initials for avatar
  function getInitials(user: { email: string; user_metadata?: { full_name?: string; name?: string } } | null): string {
    if (!user) return '?';
    const name = user.user_metadata?.full_name || user.user_metadata?.name;
    if (name) {
      return name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2);
    }
    return user.email[0].toUpperCase();
  }

  $effect(() => {
    if (isOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  });
</script>

<div class="user-menu">
  <button
    class="avatar-button"
    onclick={toggleMenu}
    aria-label="User menu"
    aria-expanded={isOpen}
  >
    {#if $isAuthenticated && $currentUser}
      {#if $currentUser.user_metadata?.avatar_url}
        <img src={$currentUser.user_metadata.avatar_url} alt="Avatar" class="avatar-image" />
      {:else}
        <span class="avatar-initials">{getInitials($currentUser)}</span>
      {/if}
    {:else}
      <svg class="avatar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 20c0-4 4-6 8-6s8 2 8 6" />
      </svg>
    {/if}
  </button>

  {#if isOpen}
    <div class="dropdown">
      {#if $isAuthenticated && $currentUser}
        <div class="dropdown-header">
          <span class="user-name">{$currentUser.user_metadata?.full_name || $currentUser.email}</span>
          <span class="user-email">{$currentUser.email}</span>
        </div>

        <div class="dropdown-divider"></div>

        <div class="context-section">
          <span class="context-label">Active Context</span>
          
          <button
            class="context-option"
            class:active={!$activeOrganization}
            onclick={switchToPersonal}
          >
            <span class="context-radio"></span>
            <span>Personal Account</span>
          </button>

          {#each $authStore.organizations as org}
            <button
              class="context-option"
              class:active={$activeOrganization?.id === org.id}
              onclick={() => switchToOrg(org.id)}
            >
              <span class="context-radio"></span>
              <span>{org.name}</span>
              <span class="role-badge">{org.role}</span>
            </button>
          {/each}
        </div>

        <div class="dropdown-divider"></div>

        <button class="dropdown-item" onclick={navigateToUpload}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 4v16m8-8H4" />
          </svg>
          Upload
        </button>

        <button class="dropdown-item" onclick={navigateToSettings}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
          </svg>
          Settings
        </button>

        <button class="dropdown-item sign-out" onclick={handleSignOut}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          Sign Out
        </button>
      {:else}
        <button class="dropdown-item" onclick={() => openAuthModal('login')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
            <polyline points="10 17 15 12 10 7" />
            <line x1="15" y1="12" x2="3" y2="12" />
          </svg>
          Sign In
        </button>

        <button class="dropdown-item" onclick={() => openAuthModal('signup')}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="8.5" cy="7" r="4" />
            <line x1="20" y1="8" x2="20" y2="14" />
            <line x1="23" y1="11" x2="17" y2="11" />
          </svg>
          Create Account
        </button>
      {/if}
    </div>
  {/if}
</div>

{#if showAuthModal}
  <AuthModal mode={authModalMode} onClose={closeAuthModal} />
{/if}

<style>
  .user-menu {
    position: fixed;
    top: var(--spacing-4);
    right: var(--spacing-4);
    z-index: 1000;
  }

  .avatar-button {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: 2px solid var(--color-border);
    background: var(--color-surface);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: border-color var(--transition-base), box-shadow var(--transition-base);
    overflow: hidden;
    padding: 0;
  }

  .avatar-button:hover {
    border-color: var(--color-primary);
    box-shadow: var(--shadow-sm);
  }

  .avatar-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .avatar-initials {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
  }

  .avatar-icon {
    width: 20px;
    height: 20px;
    color: var(--color-text-secondary);
  }

  .dropdown {
    position: absolute;
    top: calc(100% + var(--spacing-2));
    right: 0;
    min-width: 220px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    overflow: hidden;
    animation: dropdownFadeIn 0.15s ease-out;
  }

  @keyframes dropdownFadeIn {
    from {
      opacity: 0;
      transform: translateY(-8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .dropdown-header {
    padding: var(--spacing-3) var(--spacing-4);
    border-bottom: 1px solid var(--color-border);
  }

  .user-name {
    display: block;
    font-weight: var(--font-weight-medium);
    color: var(--color-text-primary);
    font-size: var(--font-size-sm);
  }

  .user-email {
    display: block;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin-top: 2px;
  }

  .dropdown-divider {
    height: 1px;
    background: var(--color-border);
  }

  .context-section {
    padding: var(--spacing-2) 0;
  }

  .context-label {
    display: block;
    padding: var(--spacing-1) var(--spacing-4);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .context-option {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    width: 100%;
    padding: var(--spacing-2) var(--spacing-4);
    background: none;
    border: none;
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    cursor: pointer;
    text-align: left;
    transition: background var(--transition-fast);
  }

  .context-option:hover {
    background: var(--color-surface-hover);
  }

  .context-radio {
    width: 14px;
    height: 14px;
    border: 2px solid var(--color-border);
    border-radius: 50%;
    flex-shrink: 0;
    position: relative;
  }

  .context-option.active .context-radio {
    border-color: var(--color-primary);
  }

  .context-option.active .context-radio::after {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 6px;
    height: 6px;
    background: var(--color-primary);
    border-radius: 50%;
  }

  .role-badge {
    margin-left: auto;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    background: var(--color-gray-100);
    padding: 1px 6px;
    border-radius: var(--radius-sm);
  }

  :global([data-theme="dark"]) .role-badge {
    background: var(--color-gray-700);
  }

  .dropdown-item {
    display: flex;
    align-items: center;
    gap: var(--spacing-3);
    width: 100%;
    padding: var(--spacing-3) var(--spacing-4);
    background: none;
    border: none;
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
    cursor: pointer;
    text-align: left;
    transition: background var(--transition-fast);
  }

  .dropdown-item:hover {
    background: var(--color-surface-hover);
  }

  .dropdown-item svg {
    width: 16px;
    height: 16px;
    color: var(--color-text-secondary);
  }

  .dropdown-item.sign-out {
    color: var(--color-error);
  }

  .dropdown-item.sign-out svg {
    color: var(--color-error);
  }
</style>
