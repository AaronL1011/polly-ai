const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  async health(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }
    return response.json();
  }

  async query(request: QueryRequest): Promise<QueryResponse> {
    const response = await fetch(`${this.baseUrl}/rag/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `Query failed: ${response.status}`);
    }

    return response.json();
  }

  async upload(file: File, options: UploadOptions = {}): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    
    if (options.title) {
      formData.append('title', options.title);
    }
    if (options.document_type) {
      formData.append('document_type', options.document_type);
    }
    if (options.source) {
      formData.append('source', options.source);
    }
    if (options.source_url) {
      formData.append('source_url', options.source_url);
    }

    const response = await fetch(`${this.baseUrl}/ingestion/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `Upload failed: ${response.status}`);
    }

    return response.json();
  }
}

export const api = new ApiClient();
