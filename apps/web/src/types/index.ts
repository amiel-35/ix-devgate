// ── Domaine DevGate ─────────────────────────────────────────────

export type UserKind = "client" | "agency";
export type EnvironmentKind = "dev" | "staging" | "preview" | "internal";
export type AccessRole = "client_member" | "reviewer" | "agency_admin";
export type AuthMethod = "magic_link" | "otp";

export interface User {
  id: string;
  email: string;
  display_name: string;
  kind: UserKind;
}

export interface Session {
  id: string;
  user: User;
  expires_at: string;
  last_seen_at: string;
  ip?: string;
  user_agent?: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  branding_name?: string;
  logo_url?: string;
  primary_color?: string;
  support_email?: string;
}

export interface Project {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description?: string;
}

export interface Environment {
  id: string;
  project_id: string;
  name: string;
  slug: string;
  kind: EnvironmentKind;
  public_hostname: string;
  requires_app_auth: boolean;
  status: "online" | "offline" | "unknown";
}

export interface EnvironmentListItem {
  id: string;
  organization_name: string;
  project_name: string;
  environment_name: string;
  kind: EnvironmentKind;
  url: string;
  requires_app_auth: boolean;
  status: "online" | "offline" | "unknown";
}

export interface AccessGrant {
  id: string;
  user_id: string;
  organization_id: string;
  role: AccessRole;
  created_at: string;
  revoked_at?: string;
}

export interface AuditEvent {
  id: string;
  actor_user_id?: string;
  event_type: string;
  target_type?: string;
  target_id?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

// ── Réponses API ─────────────────────────────────────────────────

export interface ApiError {
  detail: string;
  code?: string;
}

export interface LoginStartResponse {
  ok: boolean;
  method: AuthMethod;
}

export interface LoginVerifyResponse {
  ok: boolean;
  session_created: boolean;
  redirect_to: string;
}
