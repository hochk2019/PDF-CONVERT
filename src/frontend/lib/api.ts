const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

export type TokenResponse = {
  accessToken: string;
  tokenType: string;
};

export type UserProfile = {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
};

export type RegisterPayload = {
  email: string;
  password: string;
  full_name?: string;
  is_admin?: boolean;
};

export type JobArtifacts = Record<string, string>;

export type JobSummary = {
  id: string;
  status: string;
  input_filename: string;
  created_at: string;
  updated_at: string;
  llm_options?: Record<string, unknown> | null;
  result_payload?: (Record<string, unknown> & { artifacts?: JobArtifacts }) | null;
  error_message?: string | null;
};

export type AuditLogEntry = {
  action: string;
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
};

export type OCRConfigResponse = {
  storage_path: string;
  results_path: string;
  redis_url: string;
  celery_task_queue: string;
  llm_provider?: string | null;
  llm_model?: string | null;
  llm_base_url?: string | null;
  llm_fallback_enabled: boolean;
};

export type LLMStatusResponse = {
  primary_provider: string | null;
  fallback_enabled: boolean;
  ollama_url: string | null;
  ollama_online: boolean;
  ollama_error: string | null;
  using_external_api: boolean;
};

export type LLMOptionsPayload = Record<string, unknown>;

const jsonHeaders = (token?: string) => ({
  'Content-Type': 'application/json',
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
});

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Request failed');
  }
  return response.json() as Promise<T>;
};

export const loginRequest = async (email: string, password: string): Promise<TokenResponse> => {
  const body = new URLSearchParams({ username: email, password });
  const response = await fetch(`${API_BASE}/api/v1/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  const data = await handleResponse<{ access_token: string; token_type: string }>(response);
  return { accessToken: data.access_token, tokenType: data.token_type };
};

export const registerUser = async (payload: RegisterPayload): Promise<UserProfile> => {
  const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(payload),
  });
  return handleResponse<UserProfile>(response);
};

export const fetchCurrentUser = async (token: string): Promise<UserProfile> => {
  const response = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: jsonHeaders(token),
  });
  return handleResponse<UserProfile>(response);
};

export const uploadJob = async (
  token: string,
  file: File,
  llmOptions?: LLMOptionsPayload | null,
): Promise<{ id: string; status: string; message: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  if (llmOptions && Object.keys(llmOptions).length > 0) {
    formData.append('llm_options', JSON.stringify(llmOptions));
  }
  const response = await fetch(`${API_BASE}/api/v1/jobs`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
  });
  return handleResponse(response);
};

export const fetchJobs = async (token: string): Promise<JobSummary[]> => {
  const response = await fetch(`${API_BASE}/api/v1/jobs`, {
    headers: jsonHeaders(token),
  });
  return handleResponse<JobSummary[]>(response);
};

export const downloadResult = async (token: string, jobId: string): Promise<Blob> => {
  const response = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/result`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Unable to download result');
  }
  return response.blob();
};

export const downloadArtifact = async (
  token: string,
  jobId: string,
  kind: string,
): Promise<Blob> => {
  const response = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/artifacts/${kind}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Unable to download artifact');
  }
  return response.blob();
};

export const fetchAdminConfig = async (token: string): Promise<OCRConfigResponse> => {
  const response = await fetch(`${API_BASE}/api/v1/admin/config`, {
    headers: jsonHeaders(token),
  });
  return handleResponse<OCRConfigResponse>(response);
};

export const fetchAdminAuditLogs = async (token: string): Promise<AuditLogEntry[]> => {
  const response = await fetch(`${API_BASE}/api/v1/admin/audit-logs`, {
    headers: jsonHeaders(token),
  });
  return handleResponse<AuditLogEntry[]>(response);
};

export const fetchAdminLLMStatus = async (token: string): Promise<LLMStatusResponse> => {
  const response = await fetch(`${API_BASE}/api/v1/admin/llm-status`, {
    headers: jsonHeaders(token),
  });
  return handleResponse<LLMStatusResponse>(response);
};

export const buildJobWebSocket = (jobId: string, token: string | null): WebSocket => {
  const url = new URL(`${API_BASE.replace('http', 'ws')}/ws/jobs/${jobId}`);
  if (token) {
    url.searchParams.set('token', token);
  }
  return new WebSocket(url.toString());
};
