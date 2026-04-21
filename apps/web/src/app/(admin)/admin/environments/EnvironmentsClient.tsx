"use client";

import { useState } from "react";
import { adminApi, AdminCreateEnvPayload } from "@/lib/api/client";
import type { AdminEnvItem, OrgItem, ProjectItem } from "@/lib/api/server-admin";
import styles from "./environments.module.css";

interface Props {
  initialEnvs: AdminEnvItem[];
  orgs: OrgItem[];
  initialProjects: ProjectItem[];
}

const KIND_LABELS: Record<string, string> = {
  staging: "Staging",
  preview: "Preview",
  dev: "Dev",
  internal: "Internal",
};

const HEALTH_COLORS: Record<string, string> = {
  online: "#16a34a",
  offline: "#dc2626",
  unknown: "#d97706",
};

const HEALTH_LABELS: Record<string, string> = {
  online: "En ligne",
  offline: "Hors ligne",
  unknown: "Inconnu",
};

function KindBadge({ kind }: { kind: string }) {
  const key = `kind${kind.charAt(0).toUpperCase() + kind.slice(1)}` as keyof typeof styles;
  const cls = styles[key] ?? styles.kindInternal;
  return (
    <span className={`${styles.kindBadge} ${cls}`}>
      {KIND_LABELS[kind] ?? kind}
    </span>
  );
}

function HealthBadge({ status, latency }: { status: string | null; latency: number | null }) {
  if (!status) {
    return <span style={{ color: "#9ca3af", fontSize: "0.85em" }}>—</span>;
  }
  const color = HEALTH_COLORS[status] ?? "#6b7280";
  return (
    <span style={{
      background: color + "22",
      color,
      padding: "2px 7px",
      borderRadius: "4px",
      fontSize: "11px",
      fontWeight: 600,
    }}>
      {HEALTH_LABELS[status] ?? status}
      {latency !== null && ` · ${latency}ms`}
    </span>
  );
}

type PingState = { loading: boolean; status: string | null; latency: number | null };

export function EnvironmentsClient({ initialEnvs, orgs, initialProjects }: Props) {
  const [envs, setEnvs] = useState(initialEnvs);
  const [projects, setProjects] = useState(initialProjects);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pingStates, setPingStates] = useState<Record<string, PingState>>({});

  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [projId, setProjId] = useState("");
  const [envName, setEnvName] = useState("");
  const [envSlug, setEnvSlug] = useState("");
  const [envKind, setEnvKind] = useState("staging");
  const [hostname, setHostname] = useState("");
  const [requiresAuth, setRequiresAuth] = useState(false);

  const filteredProjects = projects.filter((p) => p.organization_id === selectedOrgId);

  function openDrawer() {
    setError(null);
    setOpen(true);
  }

  function closeDrawer() {
    setOpen(false);
    setError(null);
    setSelectedOrgId("");
    setProjId("");
    setEnvName("");
    setEnvSlug("");
    setEnvKind("staging");
    setHostname("");
    setRequiresAuth(false);
  }

  async function handlePing(envId: string) {
    setPingStates((prev) => ({ ...prev, [envId]: { loading: true, status: null, latency: null } }));
    try {
      const result = await adminApi.environments.ping(envId);
      setPingStates((prev) => ({
        ...prev,
        [envId]: { loading: false, status: result.status, latency: result.latency_ms },
      }));
    } catch {
      setPingStates((prev) => ({
        ...prev,
        [envId]: { loading: false, status: "offline", latency: null },
      }));
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload: AdminCreateEnvPayload = {
        project_id: projId,
        name: envName,
        slug: envSlug,
        kind: envKind,
        public_hostname: hostname,
        requires_app_auth: requiresAuth,
      };
      await adminApi.environments.create(payload);
      const updated = await adminApi.environments.list() as AdminEnvItem[];
      setEnvs(updated);
      closeDrawer();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Environnements</h1>
      <p className={styles.pageSub}>Toutes les ressources gérées par DevGate</p>

      <div className={styles.toolbar}>
        <span className={styles.sectionTitle}>
          {envs.length} environnement{envs.length !== 1 ? "s" : ""}
        </span>
        <button className={styles.btnPrimary} onClick={openDrawer}>
          + Nouvel environnement
        </button>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Environnement</th>
            <th>Client / Projet</th>
            <th>Type</th>
            <th>Statut</th>
            <th>Auth app</th>
            <th>Santé</th>
          </tr>
        </thead>
        <tbody>
          {envs.length === 0 ? (
            <tr className={styles.emptyRow}>
              <td colSpan={6}>Aucun environnement</td>
            </tr>
          ) : (
            envs.map((e) => {
              const ps = pingStates[e.id];
              const healthStatus = ps ? ps.status : e.health_status;
              const healthLatency = ps ? ps.latency : e.health_latency_ms;
              return (
                <tr key={e.id}>
                  <td>
                    <div className={styles.envName}>{e.name}</div>
                    <div className={styles.envHost}>{e.public_hostname}</div>
                  </td>
                  <td>
                    <span className={styles.orgProject}>
                      {e.org_name} / {e.project_name}
                    </span>
                  </td>
                  <td>
                    <KindBadge kind={e.kind} />
                  </td>
                  <td>
                    <span className={e.status === "active" ? styles.statusOnline : styles.statusInactive}>
                      {e.status === "active" ? "Actif" : e.status}
                    </span>
                  </td>
                  <td>
                    {e.requires_app_auth && (
                      <span className={styles.authBadge}>Auth requise</span>
                    )}
                  </td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <HealthBadge status={healthStatus} latency={healthLatency} />
                      <button
                        onClick={() => handlePing(e.id)}
                        disabled={ps?.loading}
                        className={styles.btnSecondary}
                        style={{ height: "26px", padding: "0 10px", fontSize: "11px" }}
                      >
                        {ps?.loading ? "…" : "Tester"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>

      {open && (
        <div className={styles.overlay} onClick={closeDrawer}>
          <div className={styles.drawer} onClick={(e) => e.stopPropagation()}>
            <div className={styles.drawerTitle}>Nouvel environnement</div>
            <form onSubmit={handleCreate}>
              <div className={styles.formGroup}>
                <label className={styles.label}>Client *</label>
                <select
                  className={styles.select}
                  value={selectedOrgId}
                  onChange={(e) => {
                    setSelectedOrgId(e.target.value);
                    setProjId("");
                  }}
                  required
                >
                  <option value="">Choisir un client…</option>
                  {orgs.map((o) => (
                    <option key={o.id} value={o.id}>{o.name}</option>
                  ))}
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Projet *</label>
                <select
                  className={styles.select}
                  value={projId}
                  onChange={(e) => setProjId(e.target.value)}
                  required
                  disabled={!selectedOrgId}
                >
                  <option value="">Choisir un projet…</option>
                  {filteredProjects.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Nom *</label>
                <input
                  className={styles.input}
                  value={envName}
                  onChange={(e) => setEnvName(e.target.value)}
                  required
                  placeholder="Staging principal"
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Slug *</label>
                <input
                  className={styles.input}
                  value={envSlug}
                  onChange={(e) => setEnvSlug(e.target.value)}
                  required
                  placeholder="staging"
                  pattern="[a-z0-9\-]+"
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Type *</label>
                <select
                  className={styles.select}
                  value={envKind}
                  onChange={(e) => setEnvKind(e.target.value)}
                >
                  <option value="staging">Staging</option>
                  <option value="preview">Preview</option>
                  <option value="dev">Dev</option>
                  <option value="internal">Internal</option>
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Hostname public *</label>
                <input
                  className={styles.input}
                  value={hostname}
                  onChange={(e) => setHostname(e.target.value)}
                  required
                  placeholder="app.client.example.com"
                />
              </div>
              <div className={styles.checkRow}>
                <input
                  id="requires-auth"
                  type="checkbox"
                  checked={requiresAuth}
                  onChange={(e) => setRequiresAuth(e.target.checked)}
                />
                <label htmlFor="requires-auth" className={styles.checkLabel}>
                  Auth applicative requise
                </label>
              </div>
              {error && <p className={styles.errorMsg}>{error}</p>}
              <div className={styles.drawerActions}>
                <button type="button" className={styles.btnSecondary} onClick={closeDrawer}>
                  Annuler
                </button>
                <button type="submit" className={styles.btnPrimary} disabled={loading}>
                  {loading ? "Création…" : "Créer"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
