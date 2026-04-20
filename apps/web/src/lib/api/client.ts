// Client API — le frontend ne connaît jamais Cloudflare
// Toutes les requêtes passent par FastAPI

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public code?: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include", // cookie de session HttpOnly
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? res.statusText, body.code);
  }

  return res.json() as Promise<T>;
}

// ── Auth ─────────────────────────────────────────────────────────

export const authApi = {
  start: (email: string) =>
    request<{ ok: boolean; method: string }>("/auth/start", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  verify: (token: string) =>
    request<{ ok: boolean; session_created: boolean; redirect_to: string }>(
      "/auth/verify",
      { method: "POST", body: JSON.stringify({ token }) },
    ),

  logout: () => request<void>("/auth/logout", { method: "POST" }),
};

// ── Portal ───────────────────────────────────────────────────────

export const portalApi = {
  me: () => request<{ id: string; email: string; display_name: string }>("/me"),

  environments: () =>
    request<
      Array<{
        id: string;
        organization_name: string;
        project_name: string;
        environment_name: string;
        kind: string;
        url: string;
        requires_app_auth: boolean;
        status: string;
      }>
    >("/me/environments"),

  sessions: () =>
    request<
      Array<{
        id: string;
        expires_at: string;
        last_seen_at: string;
        ip?: string;
        user_agent?: string;
        is_current: boolean;
      }>
    >("/me/sessions"),

  revokeSession: (sessionId: string) =>
    request<void>(`/me/sessions/${sessionId}`, { method: "DELETE" }),
};

// ── Admin ────────────────────────────────────────────────────────

export type AdminCreateOrgPayload = {
  name: string;
  slug: string;
  branding_name?: string;
  support_email?: string;
};

export type AdminCreateProjectPayload = {
  organization_id: string;
  name: string;
  slug: string;
};

export type AdminCreateEnvPayload = {
  project_id: string;
  name: string;
  slug: string;
  kind: string;
  public_hostname: string;
  upstream_hostname?: string;
  cloudflare_tunnel_id?: string;
  cloudflare_access_app_id?: string;
  service_token_ref?: string;
  requires_app_auth?: boolean;
};

export type AdminCreateGrantPayload = {
  email: string;
  organization_id: string;
  role: string;
  display_name?: string;
};

export const adminApi = {
  organizations: {
    list: () => request<unknown[]>("/admin/organizations"),
    create: (data: AdminCreateOrgPayload) =>
      request<{ id: string }>("/admin/organizations", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
  projects: {
    list: (orgId?: string) =>
      request<unknown[]>(`/admin/projects${orgId ? `?org_id=${orgId}` : ""}`),
    create: (data: AdminCreateProjectPayload) =>
      request<{ id: string }>("/admin/projects", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
  environments: {
    list: () => request<unknown[]>("/admin/environments"),
    create: (data: AdminCreateEnvPayload) =>
      request<{ id: string }>("/admin/environments", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
  grants: {
    list: () => request<unknown[]>("/admin/access-grants"),
    create: (data: AdminCreateGrantPayload) =>
      request<{ id: string }>("/admin/access-grants", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    revoke: (id: string) =>
      request<void>(`/admin/access-grants/${id}`, { method: "DELETE" }),
  },
  audit: {
    list: (params?: { limit?: number; offset?: number }) => {
      const qs = new URLSearchParams(
        Object.entries(params ?? {}).map(([k, v]) => [k, String(v)]),
      ).toString();
      return request<unknown[]>(`/admin/audit-events${qs ? `?${qs}` : ""}`);
    },
  },
};

export { ApiError };
