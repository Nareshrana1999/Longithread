// Thin typed client for the Longithread backend. Tenant scoping is a header in
// the MVP; replace with real auth tokens + a server-side session before pilots.
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export type TenantHeaders = { "x-tenant-id": string; "x-user-role"?: string };

async function call<T>(path: string, headers: TenantHeaders, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...headers, ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  listPatients: (h: TenantHeaders) => call<unknown[]>("/patients", h),
  createPatient: (h: TenantHeaders, condition: string) =>
    call<{ id: string }>("/patients", h, { method: "POST", body: JSON.stringify({ condition }) }),
  timeline: (h: TenantHeaders, pid: string) => call<unknown[]>(`/patients/${pid}/timeline`, h),
  risk: (h: TenantHeaders, pid: string) => call<unknown>(`/patients/${pid}/risk`, h),
  generateTasks: (h: TenantHeaders, pid: string, protocol: string) =>
    call<unknown[]>(`/patients/${pid}/tasks/generate?protocol=${protocol}`, h, { method: "POST" }),
  cohort: (h: TenantHeaders) => call<unknown>("/analytics/cohort", h),
};
