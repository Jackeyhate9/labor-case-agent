const DEFAULT_API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_BASE_STORAGE_KEY = "labor-case-api-base";
const launchFragment =
  typeof window === "undefined"
    ? null
    : new URLSearchParams(window.location.hash.replace(/^#/, ""));
const launchApiBase = launchFragment?.get("api_base") ?? "";
if (
  typeof window !== "undefined" &&
  /^http:\/\/127\.0\.0\.1:\d+$/.test(launchApiBase)
) {
  window.sessionStorage.setItem(API_BASE_STORAGE_KEY, launchApiBase);
}
export const API_BASE =
  (typeof window !== "undefined" &&
    window.sessionStorage.getItem(API_BASE_STORAGE_KEY)) ||
  DEFAULT_API_BASE;
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const SESSION_STORAGE_KEY = "labor-case-session";

function desktopSessionToken(): string {
  if (typeof window === "undefined") return "";
  const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const fromLaunch = fragment.get("app_session") ?? "";
  if (fromLaunch) {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, fromLaunch);
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${window.location.search}`,
    );
    return fromLaunch;
  }
  return window.sessionStorage.getItem(SESSION_STORAGE_KEY) ?? "";
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const sessionToken = desktopSessionToken();
  if (sessionToken) headers.set("X-App-Session", sessionToken);
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    let message = `请求失败（${res.status}）`;
    try {
      const body = await res.json();
      message = body.error?.message ?? body.detail ?? body.message ?? message;
    } catch {}
    throw new ApiError(res.status, message);
  }
  const type = res.headers.get("content-type") ?? "";
  if (type.includes("application/json")) {
    const data = await res.json();
    return (data.data ?? data) as T;
  }
  return (await res.blob()) as T;
}
export type CaseItem = {
  id: string;
  title: string;
  case_type?: string;
  status?: string;
  jurisdiction_region?: string;
  summary?: string;
  created_at?: string;
  updated_at?: string;
};
export type Fact = {
  id: string;
  fact_type?: string;
  predicate?: string;
  object_value?: string;
  normalized_value?: string;
  source_quote?: string;
  source_evidence_id?: string;
  source_page?: number;
  machine_confidence?: number;
  review_status: string;
  user_corrected_value?: string;
  date_value?: string;
  amount_value?: number;
};
export type Evidence = {
  id: string;
  evidence_number?: string;
  original_filename: string;
  document_type?: string;
  processing_status?: string;
  ocr_status?: string;
  review_status?: string;
  file_size?: number;
  source_description?: string;
};
export const listCases = () => api<CaseItem[]>("/api/cases");
export const getCase = (id: string) => api<CaseItem>(`/api/cases/${id}`);
export const post = (path: string, data?: unknown) =>
  api<any>(path, {
    method: "POST",
    body: data === undefined ? undefined : JSON.stringify(data),
  });
export const patch = (path: string, data: unknown) =>
  api<any>(path, { method: "PATCH", body: JSON.stringify(data) });
