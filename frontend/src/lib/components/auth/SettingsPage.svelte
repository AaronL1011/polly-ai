<script lang="ts">
  import { authStore, isAuthenticated, currentUser, activeOrganization, type Organization } from '$lib/stores/auth';
  import { api, type MembershipResponse, type BillingAccountResponse, type CreditPackResponse, type TransactionResponse } from '$lib/api/client';

  type Tab = 'profile' | 'organizations' | 'billing';
  let activeTab = $state<Tab>('profile');

  // Profile state
  let displayName = $state('');
  let avatarUrl = $state('');
  let profileSaving = $state(false);
  let profileMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);

  // Organizations state - use the auth store's organizations which include role
  let selectedOrg = $state<Organization | null>(null);
  let orgMembers = $state<MembershipResponse[]>([]);
  let showCreateOrg = $state(false);
  let newOrgName = $state('');
  let newOrgSlug = $state('');
  let newOrgEmail = $state('');
  let orgLoading = $state(false);
  let orgError = $state<string | null>(null);
  let inviteEmail = $state('');
  let inviteRole = $state('member');

  // Billing state
  let billingAccount = $state<BillingAccountResponse | null>(null);
  let creditPacks = $state<CreditPackResponse[]>([]);
  let transactions = $state<TransactionResponse[]>([]);
  let billingLoading = $state(false);
  let purchaseLoading = $state(false);

  // Sync auth token with API client
  $effect(() => {
    const token = $authStore.session?.access_token ?? null;
    api.setAccessToken(token);
  });

  // Sync organization context with API client
  $effect(() => {
    const orgId = $authStore.activeContext === 'personal' ? null : $authStore.activeContext;
    api.setOrganizationId(orgId);
  });

  // Initialize profile data
  $effect(() => {
    if ($currentUser) {
      displayName = $currentUser.user_metadata?.full_name || $currentUser.user_metadata?.name || '';
      avatarUrl = $currentUser.user_metadata?.avatar_url || '';
    }
  });

  // Organizations come from the auth store which already has role info
  let organizations = $derived($authStore.organizations);

  // Fetch billing data
  $effect(() => {
    if ($isAuthenticated && activeTab === 'billing') {
      loadBillingData();
    }
  });

  async function loadBillingData() {
    billingLoading = true;
    try {
      const [account, packs, txns] = await Promise.all([
        api.getBillingAccount(),
        api.getCreditPacks(),
        api.getTransactions(20),
      ]);
      billingAccount = account;
      creditPacks = packs;
      transactions = txns;
    } catch (e) {
      console.error('Failed to load billing data:', e);
    } finally {
      billingLoading = false;
    }
  }

  async function selectOrg(org: Organization) {
    selectedOrg = org;
    try {
      orgMembers = await api.getOrganizationMembers(org.slug);
    } catch (e) {
      console.error('Failed to load members:', e);
      orgMembers = [];
    }
  }

  async function createOrganization() {
    if (!newOrgName || !newOrgSlug || !newOrgEmail) {
      orgError = 'Please fill in all fields';
      return;
    }

    orgLoading = true;
    orgError = null;

    try {
      await api.createOrganization({
        name: newOrgName,
        slug: newOrgSlug,
        billing_email: newOrgEmail,
      });
      showCreateOrg = false;
      newOrgName = '';
      newOrgSlug = '';
      newOrgEmail = '';
      // Refresh organizations from auth store
      await authStore.refreshOrganizations();
    } catch (e) {
      orgError = e instanceof Error ? e.message : 'Failed to create organization';
    } finally {
      orgLoading = false;
    }
  }

  async function inviteMember() {
    if (!selectedOrg || !inviteEmail) return;

    orgLoading = true;
    orgError = null;

    try {
      await api.inviteMember(selectedOrg.slug, { email: inviteEmail, role: inviteRole });
      inviteEmail = '';
      // Refresh members list
      orgMembers = await api.getOrganizationMembers(selectedOrg.slug);
    } catch (e) {
      orgError = e instanceof Error ? e.message : 'Failed to send invitation';
    } finally {
      orgLoading = false;
    }
  }

  async function purchaseCredits(packIndex: number) {
    purchaseLoading = true;
    try {
      const currentUrl = window.location.origin;
      const checkout = await api.purchaseCredits(
        packIndex,
        `${currentUrl}/settings?tab=billing&success=true`,
        `${currentUrl}/settings?tab=billing`
      );
      // Redirect to Stripe checkout
      window.location.href = checkout.checkout_url;
    } catch (e) {
      console.error('Failed to create checkout:', e);
    } finally {
      purchaseLoading = false;
    }
  }

  function navigateHome() {
    window.history.pushState({}, '', '/');
    window.dispatchEvent(new PopStateEvent('popstate'));
  }

  function generateSlug(name: string): string {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 40);
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('en-AU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  }

  function formatCredits(amount: number): string {
    const sign = amount >= 0 ? '+' : '';
    return `${sign}${amount}`;
  }
</script>

<div class="settings-page">
  <header class="settings-header">
    <button class="back-link" onclick={navigateHome}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="15 18 9 12 15 6" />
      </svg>
      Back to Home
    </button>
    <h1>Settings</h1>
  </header>

  {#if !$isAuthenticated}
    <div class="not-authenticated">
      <p>Please sign in to access settings.</p>
    </div>
  {:else}
    <nav class="tabs">
      <button
        class="tab"
        class:active={activeTab === 'profile'}
        onclick={() => activeTab = 'profile'}
      >
        Profile
      </button>
      <button
        class="tab"
        class:active={activeTab === 'organizations'}
        onclick={() => activeTab = 'organizations'}
      >
        Organizations
      </button>
      <button
        class="tab"
        class:active={activeTab === 'billing'}
        onclick={() => activeTab = 'billing'}
      >
        Billing
      </button>
    </nav>

    <div class="tab-content">
      {#if activeTab === 'profile'}
        <section class="settings-section">
          <h2>Profile Information</h2>
          
          <div class="form-group">
            <label for="email">Email</label>
            <input
              id="email"
              type="email"
              value={$currentUser?.email || ''}
              disabled
              class="input-disabled"
            />
            <span class="field-hint">Email cannot be changed</span>
          </div>

          <div class="form-group">
            <label for="display-name">Display Name</label>
            <input
              id="display-name"
              type="text"
              bind:value={displayName}
              placeholder="Your name"
            />
          </div>

          <div class="form-group">
            <label for="avatar-url">Avatar URL</label>
            <input
              id="avatar-url"
              type="url"
              bind:value={avatarUrl}
              placeholder="https://example.com/avatar.jpg"
            />
          </div>

          {#if profileMessage}
            <div class="message {profileMessage.type}">{profileMessage.text}</div>
          {/if}

          <button class="btn-primary" disabled={profileSaving}>
            {profileSaving ? 'Saving...' : 'Save Changes'}
          </button>
        </section>

      {:else if activeTab === 'organizations'}
        <section class="settings-section">
          <div class="section-header">
            <h2>Your Organizations</h2>
            <button class="btn-secondary" onclick={() => showCreateOrg = !showCreateOrg}>
              {showCreateOrg ? 'Cancel' : '+ Create Organization'}
            </button>
          </div>

          {#if showCreateOrg}
            <div class="create-org-form">
              <div class="form-group">
                <label for="org-name">Organization Name</label>
                <input
                  id="org-name"
                  type="text"
                  bind:value={newOrgName}
                  placeholder="Acme Corp"
                  oninput={() => newOrgSlug = generateSlug(newOrgName)}
                />
              </div>

              <div class="form-group">
                <label for="org-slug">URL Slug</label>
                <input
                  id="org-slug"
                  type="text"
                  bind:value={newOrgSlug}
                  placeholder="acme-corp"
                />
                <span class="field-hint">Used in URLs: /orgs/{newOrgSlug || 'slug'}</span>
              </div>

              <div class="form-group">
                <label for="org-email">Billing Email</label>
                <input
                  id="org-email"
                  type="email"
                  bind:value={newOrgEmail}
                  placeholder="billing@acme.com"
                />
              </div>

              {#if orgError}
                <div class="message error">{orgError}</div>
              {/if}

              <button class="btn-primary" onclick={createOrganization} disabled={orgLoading}>
                {orgLoading ? 'Creating...' : 'Create Organization'}
              </button>
            </div>
          {/if}

          <div class="org-list">
            {#each organizations as org}
              <button
                class="org-item"
                class:selected={selectedOrg?.id === org.id}
                onclick={() => selectOrg(org)}
              >
                <span class="org-name">{org.name}</span>
                <span class="org-role">{org.role}</span>
              </button>
            {:else}
              <p class="empty-state">You're not a member of any organizations yet.</p>
            {/each}
          </div>

          {#if selectedOrg}
            <div class="org-details">
              <h3>{selectedOrg.name}</h3>
              <p class="org-meta">
                {selectedOrg.member_count || 0} members · {selectedOrg.plan} plan
              </p>

              <h4>Members</h4>
              <ul class="member-list">
                {#each orgMembers as member}
                  <li class="member-item">
                    <span>{member.user_email || member.user_id}</span>
                    <span class="member-role">{member.role}</span>
                  </li>
                {:else}
                  <li class="empty-state">No members found</li>
                {/each}
              </ul>

              {#if selectedOrg.role === 'owner' || selectedOrg.role === 'admin'}
                <div class="invite-form">
                  <h4>Invite Member</h4>
                  <div class="invite-row">
                    <input
                      type="email"
                      bind:value={inviteEmail}
                      placeholder="member@example.com"
                    />
                    <select bind:value={inviteRole}>
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                      <option value="viewer">Viewer</option>
                    </select>
                    <button class="btn-secondary" onclick={inviteMember} disabled={orgLoading}>
                      Invite
                    </button>
                  </div>
                </div>
              {/if}
            </div>
          {/if}
        </section>

      {:else if activeTab === 'billing'}
        <section class="settings-section">
          <h2>Billing & Credits</h2>

          {#if billingLoading}
            <div class="loading">Loading billing information...</div>
          {:else if billingAccount}
            <div class="balance-card">
              <div class="balance-item">
                <span class="balance-label">Available Credits</span>
                <span class="balance-value">{billingAccount.credits}</span>
              </div>
              <div class="balance-item">
                <span class="balance-label">Free Tier Remaining</span>
                <span class="balance-value">{billingAccount.free_tier_remaining}</span>
              </div>
              {#if billingAccount.free_tier_reset_at}
                <div class="balance-reset">
                  Resets {formatDate(billingAccount.free_tier_reset_at)}
                </div>
              {/if}
            </div>

            <h3>Purchase Credits</h3>
            <div class="credit-packs">
              {#each creditPacks as pack, index}
                <button
                  class="credit-pack"
                  onclick={() => purchaseCredits(index)}
                  disabled={purchaseLoading}
                >
                  <span class="pack-credits">{pack.credits} credits</span>
                  <span class="pack-price">${pack.price_dollars.toFixed(2)}</span>
                </button>
              {/each}
            </div>

            <h3>Recent Transactions</h3>
            <div class="transactions">
              {#each transactions as tx}
                <div class="transaction-item">
                  <div class="tx-info">
                    <span class="tx-type">{tx.transaction_type}</span>
                    <span class="tx-desc">{tx.description || 'Transaction'}</span>
                  </div>
                  <div class="tx-meta">
                    <span class="tx-amount" class:positive={tx.amount > 0} class:negative={tx.amount < 0}>
                      {formatCredits(tx.amount)}
                    </span>
                    <span class="tx-date">{formatDate(tx.created_at)}</span>
                  </div>
                </div>
              {:else}
                <p class="empty-state">No transactions yet</p>
              {/each}
            </div>
          {:else}
            <p class="empty-state">Unable to load billing information</p>
          {/if}
        </section>
      {/if}
    </div>
  {/if}
</div>

<style>
  .settings-page {
    min-height: 100vh;
    background: var(--color-background);
    padding: var(--spacing-6);
  }

  .settings-header {
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

  .settings-header h1 {
    font-family: 'Literata', serif;
    font-size: var(--font-size-3xl);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-heading);
    margin: 0;
  }

  .not-authenticated {
    max-width: var(--max-width-md);
    margin: 0 auto;
    text-align: center;
    padding: var(--spacing-8);
    background: var(--color-surface);
    border-radius: var(--radius-lg);
    color: var(--color-text-secondary);
  }

  .tabs {
    max-width: var(--max-width-md);
    margin: 0 auto var(--spacing-6);
    display: flex;
    gap: var(--spacing-1);
    border-bottom: 1px solid var(--color-border);
  }

  .tab {
    padding: var(--spacing-3) var(--spacing-4);
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--color-text-secondary);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: color var(--transition-fast), border-color var(--transition-fast);
    margin-bottom: -1px;
  }

  .tab:hover {
    color: var(--color-text-primary);
  }

  .tab.active {
    color: var(--color-primary);
    border-bottom-color: var(--color-primary);
  }

  .tab-content {
    max-width: var(--max-width-md);
    margin: 0 auto;
  }

  .settings-section {
    background: var(--color-surface);
    border-radius: var(--radius-lg);
    padding: var(--spacing-6);
    border: 1px solid var(--color-border);
  }

  .settings-section h2 {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-heading);
    margin: 0 0 var(--spacing-4);
  }

  .settings-section h3 {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-heading);
    margin: var(--spacing-6) 0 var(--spacing-3);
  }

  .settings-section h4 {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-primary);
    margin: var(--spacing-4) 0 var(--spacing-2);
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-4);
  }

  .section-header h2 {
    margin: 0;
  }

  .form-group {
    margin-bottom: var(--spacing-4);
  }

  .form-group label {
    display: block;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-primary);
    margin-bottom: var(--spacing-1);
  }

  .form-group input {
    width: 100%;
    padding: var(--spacing-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    background: var(--color-surface);
    color: var(--color-text-primary);
    transition: border-color var(--transition-fast);
  }

  .form-group input:focus {
    outline: none;
    border-color: var(--color-primary);
  }

  .input-disabled {
    background: var(--color-gray-100);
    color: var(--color-text-muted);
  }

  .field-hint {
    display: block;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin-top: var(--spacing-1);
  }

  .message {
    padding: var(--spacing-3);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    margin-bottom: var(--spacing-4);
  }

  .message.success {
    background: var(--color-success-light);
    color: var(--color-success-text);
  }

  .message.error {
    background: var(--color-error-light);
    color: var(--color-error-text);
  }

  .btn-primary {
    padding: var(--spacing-3) var(--spacing-4);
    background: var(--color-primary);
    color: var(--color-text-inverse);
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: background var(--transition-fast);
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--color-primary-hover);
  }

  .btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-secondary {
    padding: var(--spacing-2) var(--spacing-3);
    background: var(--color-surface);
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: border-color var(--transition-fast), background var(--transition-fast);
  }

  .btn-secondary:hover:not(:disabled) {
    border-color: var(--color-primary);
    background: var(--color-primary-light);
  }

  .btn-secondary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .create-org-form {
    padding: var(--spacing-4);
    border-radius: var(--radius-md);
    margin-bottom: var(--spacing-4);
  }

  .org-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .org-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-3) var(--spacing-4);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: border-color var(--transition-fast);
    text-align: left;
    width: 100%;
  }

  .org-item:hover {
    border-color: var(--color-primary);
  }

  .org-item.selected {
    border-color: var(--color-primary);
    background: var(--color-primary-light);
  }

  .org-name {
    font-weight: var(--font-weight-medium);
    color: var(--color-text-primary);
  }

  .org-role {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    background: var(--color-gray-100);
    padding: 2px 8px;
    border-radius: var(--radius-sm);
  }

  .org-details {
    margin-top: var(--spacing-4);
    padding-top: var(--spacing-4);
    border-top: 1px solid var(--color-border);
  }

  .org-details h3 {
    margin-top: 0;
  }

  .org-meta {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
    margin: 0 0 var(--spacing-4);
  }

  .member-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .member-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-2) 0;
    border-bottom: 1px solid var(--color-border-light);
    font-size: var(--font-size-sm);
  }

  .member-role {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .invite-form {
    margin-top: var(--spacing-4);
    padding-top: var(--spacing-4);
    border-top: 1px solid var(--color-border);
  }

  .invite-row {
    display: flex;
    gap: var(--spacing-2);
  }

  .invite-row input {
    flex: 1;
  }

  .invite-row select {
    width: 120px;
  }

  .empty-state {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    text-align: center;
    padding: var(--spacing-4);
  }

  .loading {
    text-align: center;
    color: var(--color-text-secondary);
    padding: var(--spacing-6);
  }

  .balance-card {
    background: var(--color-primary-light);
    border-radius: var(--radius-lg);
    padding: var(--spacing-4);
    display: flex;
    gap: var(--spacing-6);
    flex-wrap: wrap;
    margin-bottom: var(--spacing-4);
  }

  .balance-item {
    display: flex;
    flex-direction: column;
  }

  .balance-label {
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .balance-value {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-semibold);
    color: var(--color-primary);
  }

  .balance-reset {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin-left: auto;
    align-self: center;
  }

  .credit-packs {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: var(--spacing-3);
    margin-bottom: var(--spacing-4);
  }

  .credit-pack {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--spacing-4);
    background: var(--color-surface);
    border: 2px solid var(--color-border);
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: border-color var(--transition-fast), transform var(--transition-fast);
  }

  .credit-pack:hover:not(:disabled) {
    border-color: var(--color-primary);
    transform: translateY(-2px);
  }

  .credit-pack:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .pack-credits {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-heading);
  }

  .pack-price {
    font-size: var(--font-size-sm);
    color: var(--color-primary);
    font-weight: var(--font-weight-medium);
  }

  .transactions {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .transaction-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-3);
    background: var(--color-gray-50);
    border-radius: var(--radius-md);
  }

  .tx-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .tx-type {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    text-transform: capitalize;
  }

  .tx-desc {
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
  }

  .tx-meta {
    text-align: right;
  }

  .tx-amount {
    display: block;
    font-weight: var(--font-weight-semibold);
    font-size: var(--font-size-sm);
  }

  .tx-amount.positive {
    color: var(--color-success);
  }

  .tx-amount.negative {
    color: var(--color-error);
  }

  .tx-date {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  @media (prefers-color-scheme: dark) {
    .input-disabled {
      background: var(--color-gray-800);
    }

    .org-role {
      background: var(--color-gray-700);
    }

    .transaction-item {
      background: var(--color-gray-800);
    }
  }
</style>
