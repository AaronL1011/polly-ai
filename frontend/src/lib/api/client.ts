const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// =============================================================================
// Query Types
// =============================================================================

export interface QueryRequest {
  query: string;
  filters?: {
    document_types?: string[];
    date_from?: string;
    date_to?: string;
    sources?: string[];
    member_ids?: string[];
  };
}

export type ComponentSize = 'full' | 'half' | 'third' | 'two-thirds' | 'auto';
export type SectionLayout = 'stack' | 'grid' | 'two-column' | 'three-column';

export interface ComponentData {
  id: string;
  type: string;
  data: Record<string, unknown>;
  size?: ComponentSize;
}

export interface SectionData {
  title?: string;
  component_ids: string[];
  layout?: SectionLayout;
}

export interface LayoutData {
  title?: string;
  subtitle?: string;
  sections: SectionData[];
}

export interface CostBreakdown {
  embedding_tokens: number;
  llm_input_tokens: number;
  llm_output_tokens: number;
  total_cents: number;
  total_credits: number;
}

export interface QueryMetadata {
  documents_retrieved: number;
  chunks_used: number;
  processing_time_ms: number;
  model: string;
}

export interface SourceReference {
  document_id: string;
  source_name: string;
  source_url?: string;
  source_date?: string;
}

export interface QueryResponse {
  layout: LayoutData;
  components: ComponentData[];
  cost: CostBreakdown;
  cached: boolean;
  metadata: QueryMetadata;
  sources: SourceReference[];
}

export interface HealthResponse {
  status: string;
}

export interface UploadOptions {
  title?: string;
  document_type?: string;
  source?: string;
  source_url?: string;
}

export interface UploadResponse {
  job_id: string;
  status: string;
  progress_percent: number;
}

// =============================================================================
// Auth Types
// =============================================================================

export interface UserResponse {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  email_verified: boolean;
}

export interface SessionResponse {
  user: UserResponse;
  expires_at?: string;
}

// =============================================================================
// Organization Types
// =============================================================================

export interface OrganizationResponse {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  billing_email: string;
  plan: string;
  max_seats: number;
  member_count?: number;
}

export interface MembershipResponse {
  id: string;
  user_id: string;
  organization_id: string;
  role: string;
  joined_at: string;
  user_email?: string;
  user_name?: string;
}

export interface InvitationResponse {
  id: string;
  email: string;
  organization_id: string;
  role: string;
  status: string;
  expires_at: string;
  created_at: string;
}

export interface CreateOrganizationRequest {
  name: string;
  slug: string;
  billing_email: string;
}

export interface InviteMemberRequest {
  email: string;
  role?: string;
}

// =============================================================================
// Billing Types
// =============================================================================

export interface BillingAccountResponse {
  id: string;
  account_type: 'user' | 'organization';
  credits: number;
  free_tier_remaining: number;
  free_tier_reset_at: string | null;
  lifetime_credits: number;
  lifetime_usage: number;
  has_stripe_customer: boolean;
}

export interface CreditPackResponse {
  credits: number;
  price_cents: number;
  price_dollars: number;
}

export interface TransactionResponse {
  id: string;
  amount: number;
  transaction_type: string;
  balance_after: number;
  description: string | null;
  reference_id: string | null;
  created_at: string;
}

export interface CheckoutResponse {
  session_id: string;
  checkout_url: string;
  expires_at: string;
}

export interface UsageSummaryResponse {
  total_usage: number;
  total_purchases: number;
  period_start: string;
  period_end: string;
}

// =============================================================================
// API Client
// =============================================================================

class ApiClient {
  private baseUrl: string;
  private accessToken: string | null = null;
  private organizationId: string | null = null;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  // Set the access token for authenticated requests
  setAccessToken(token: string | null) {
    this.accessToken = token;
  }

  // Set the active organization context
  setOrganizationId(orgId: string | null) {
    this.organizationId = orgId;
  }

  // Build headers for requests
  private getHeaders(includeContentType = true): HeadersInit {
    const headers: Record<string, string> = {};
    
    if (includeContentType) {
      headers['Content-Type'] = 'application/json';
    }
    
    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }
    
    if (this.organizationId) {
      headers['X-Organization-Id'] = this.organizationId;
    }
    
    return headers;
  }

  // Generic request helper
  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        ...this.getHeaders(options.method !== 'GET'),
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `Request failed: ${response.status}`);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  // ==========================================================================
  // Health
  // ==========================================================================

  async health(): Promise<HealthResponse> {
    return this.request('/health');
  }

  // ==========================================================================
  // RAG Query
  // ==========================================================================

  async query(request: QueryRequest): Promise<QueryResponse> {
    return this.request('/rag/query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // ==========================================================================
  // Ingestion
  // ==========================================================================

  async upload(file: File, options: UploadOptions = {}): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    
    if (options.title) formData.append('title', options.title);
    if (options.document_type) formData.append('document_type', options.document_type);
    if (options.source) formData.append('source', options.source);
    if (options.source_url) formData.append('source_url', options.source_url);

    const response = await fetch(`${this.baseUrl}/ingestion/upload`, {
      method: 'POST',
      headers: this.accessToken ? { 'Authorization': `Bearer ${this.accessToken}` } : {},
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `Upload failed: ${response.status}`);
    }

    return response.json();
  }

  // ==========================================================================
  // Auth
  // ==========================================================================

  async getSession(): Promise<SessionResponse> {
    return this.request('/auth/session');
  }

  async logout(): Promise<void> {
    return this.request('/auth/logout', { method: 'POST' });
  }

  // ==========================================================================
  // Organizations
  // ==========================================================================

  async getOrganizations(): Promise<OrganizationResponse[]> {
    return this.request('/orgs');
  }

  async getOrganization(slug: string): Promise<OrganizationResponse> {
    return this.request(`/orgs/${slug}`);
  }

  async createOrganization(data: CreateOrganizationRequest): Promise<OrganizationResponse> {
    return this.request('/orgs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateOrganization(
    slug: string,
    data: Partial<Pick<OrganizationResponse, 'name' | 'billing_email'>>
  ): Promise<OrganizationResponse> {
    return this.request(`/orgs/${slug}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteOrganization(slug: string): Promise<void> {
    return this.request(`/orgs/${slug}`, { method: 'DELETE' });
  }

  async getOrganizationMembers(slug: string): Promise<MembershipResponse[]> {
    return this.request(`/orgs/${slug}/members`);
  }

  async inviteMember(slug: string, data: InviteMemberRequest): Promise<InvitationResponse> {
    return this.request(`/orgs/${slug}/members`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async removeMember(slug: string, memberId: string): Promise<void> {
    return this.request(`/orgs/${slug}/members/${memberId}`, { method: 'DELETE' });
  }

  async getOrganizationInvitations(slug: string): Promise<InvitationResponse[]> {
    return this.request(`/orgs/${slug}/invitations`);
  }

  async acceptInvitation(token: string): Promise<MembershipResponse> {
    return this.request(`/orgs/invitations/${token}/accept`, { method: 'POST' });
  }

  async declineInvitation(token: string): Promise<void> {
    return this.request(`/orgs/invitations/${token}/decline`, { method: 'POST' });
  }

  // ==========================================================================
  // Billing
  // ==========================================================================

  async getCreditPacks(): Promise<CreditPackResponse[]> {
    return this.request('/billing/packs');
  }

  async getBillingAccount(): Promise<BillingAccountResponse> {
    return this.request('/billing/account');
  }

  async purchaseCredits(
    packIndex: number,
    successUrl: string,
    cancelUrl: string
  ): Promise<CheckoutResponse> {
    return this.request('/billing/credits/purchase', {
      method: 'POST',
      body: JSON.stringify({
        credit_pack_index: packIndex,
        success_url: successUrl,
        cancel_url: cancelUrl,
      }),
    });
  }

  async getTransactions(limit = 50, offset = 0): Promise<TransactionResponse[]> {
    return this.request(`/billing/transactions?limit=${limit}&offset=${offset}`);
  }

  async getUsageSummary(days = 30): Promise<UsageSummaryResponse> {
    return this.request(`/billing/usage/summary?days=${days}`);
  }
}

export const api = new ApiClient();
