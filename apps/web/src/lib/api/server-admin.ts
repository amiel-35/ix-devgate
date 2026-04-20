// Helper pour appeler les routes /admin/* depuis les Server Components.
// Mêmes conventions que server.ts : forwarding du cookie devgate_session.
// Les routes admin retournent 403 si le rôle n'est pas agency_admin.

import { cookies } from "next/headers";

const API_BASE =
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8001";

export class AdminApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "AdminApiError";
  }
}

async function adminRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Cookie: cookieHeader,
      ...options.headers,
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new AdminApiError(res.status, body.detail ?? res.statusText);
  }

  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────

export type OrgItem = {
  id: string;
  name: string;
  slug: string;
  branding_name: string | null;
  support_email: string | null;
  env_count: number;
  user_count: number;
};

export type ProjectItem = {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
};

export type AdminEnvItem = {
  id: string;
  project_id: string;
  name: string;
  slug: string;
  kind: string;
  public_hostname: string;
  requires_app_auth: boolean;
  status: string;
  org_name: string;
  project_name: string;
};

export type GrantItem = {
  id: string;
  user_id: string;
  user_email: string;
  organization_id: string;
  org_name: string;
  role: string;
  created_at: string;
  revoked_at: string | null;
};

export type AdminAuditEvent = {
  id: string;
  actor_user_id: string | null;
  event_type: string;
  target_type: string | null;
  target_id: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
};

export type StatsResponse = {
  active_orgs: number;
  active_envs: number;
  active_users: number;
  events_today: number;
};

// ── API Admin (server-side) ───────────────────────────────────────

export const serverAdminApi = {
  stats: () => adminRequest<StatsResponse>("/admin/stats"),
  organizations: () => adminRequest<OrgItem[]>("/admin/organizations"),
  projects: (orgId?: string) =>
    adminRequest<ProjectItem[]>(`/admin/projects${orgId ? `?org_id=${orgId}` : ""}`),
  environments: () => adminRequest<AdminEnvItem[]>("/admin/environments"),
  grants: () => adminRequest<GrantItem[]>("/admin/access-grants"),
  auditEvents: (limit = 50, offset = 0) =>
    adminRequest<AdminAuditEvent[]>(`/admin/audit-events?limit=${limit}&offset=${offset}`),
};
