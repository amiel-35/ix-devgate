// Helper pour appeler l'API depuis les Server Components.
// Les Server Components ne transmettent pas automatiquement les cookies :
// on les lit de next/headers et on les forward dans l'en-tête Cookie.

import { cookies } from "next/headers";

// API_INTERNAL_URL est utilisé par les Server Components (réseau Docker interne).
// NEXT_PUBLIC_API_URL est utilisé par le navigateur (adresse accessible depuis l'extérieur).
const API_BASE =
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8001";

export class ServerApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ServerApiError";
  }
}

async function serverRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
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
    cache: "no-store", // toujours fraîche — pas de cache statique sur les données utilisateur
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ServerApiError(res.status, body.detail ?? res.statusText);
  }

  return res.json() as Promise<T>;
}

// ── Types partagés ────────────────────────────────────────────────

export type MeResponse = {
  id: string;
  email: string;
  display_name: string | null;
};

export type EnvironmentItem = {
  id: string;
  organization_name: string;
  project_name: string;
  environment_name: string;
  kind: string;
  url: string;
  gateway_url: string; // Chemin gateway — ex: "/gateway/abc123/"
  requires_app_auth: boolean;
  status: string; // "online" | "offline" | "unknown"
};

export type SessionItem = {
  id: string;
  expires_at: string;
  last_seen_at: string;
  ip: string | null;
  user_agent: string | null;
  is_current: boolean;
};

// ── API Portal (server-side) ──────────────────────────────────────

export const serverPortalApi = {
  me: () => serverRequest<MeResponse>("/me"),
  environments: () => serverRequest<EnvironmentItem[]>("/me/environments"),
  sessions: () => serverRequest<SessionItem[]>("/me/sessions"),
};
