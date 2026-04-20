"use client";

import { useState } from "react";
import { adminApi, AdminCreateGrantPayload } from "@/lib/api/client";
import type { GrantItem, OrgItem } from "@/lib/api/server-admin";
import styles from "./access.module.css";

interface Props {
  initialGrants: GrantItem[];
  orgs: OrgItem[];
}

function RoleBadge({ role, revoked }: { role: string; revoked: boolean }) {
  if (revoked) return <span className={styles.roleRevoked}>Révoqué</span>;
  if (role === "agency_admin") return <span className={styles.roleAdmin}>Admin agence</span>;
  return (
    <span className={styles.roleMember}>
      {role === "client_member" ? "Membre client" : role}
    </span>
  );
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function AccessClient({ initialGrants, orgs }: Props) {
  const [grants, setGrants] = useState(initialGrants);
  const [open, setOpen] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [orgId, setOrgId] = useState("");
  const [role, setRole] = useState("client_member");
  const [displayName, setDisplayName] = useState("");

  function openDrawer() {
    setError(null);
    setOpen(true);
  }

  function closeDrawer() {
    setOpen(false);
    setError(null);
    setEmail("");
    setOrgId("");
    setRole("client_member");
    setDisplayName("");
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload: AdminCreateGrantPayload = {
        email,
        organization_id: orgId,
        role,
        display_name: displayName || undefined,
      };
      await adminApi.grants.create(payload);
      const updated = await adminApi.grants.list() as GrantItem[];
      setGrants(updated);
      closeDrawer();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  async function handleRevoke(grantId: string) {
    setRevokingId(grantId);
    try {
      await adminApi.grants.revoke(grantId);
      setGrants((prev) =>
        prev.map((g) =>
          g.id === grantId ? { ...g, revoked_at: new Date().toISOString() } : g,
        ),
      );
    } finally {
      setRevokingId(null);
    }
  }

  const active = grants.filter((g) => !g.revoked_at);
  const revoked = grants.filter((g) => !!g.revoked_at);

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Accès</h1>
      <p className={styles.pageSub}>Gestion des accès utilisateurs par organisation</p>

      <div className={styles.toolbar}>
        <span className={styles.sectionTitle}>
          {active.length} accès actif{active.length !== 1 ? "s" : ""}
        </span>
        <button className={styles.btnPrimary} onClick={openDrawer}>
          + Inviter un utilisateur
        </button>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Utilisateur</th>
            <th>Organisation</th>
            <th>Rôle</th>
            <th>Accordé le</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {grants.length === 0 ? (
            <tr className={styles.emptyRow}>
              <td colSpan={5}>Aucun accès configuré</td>
            </tr>
          ) : (
            [...active, ...revoked].map((g) => (
              <tr key={g.id}>
                <td>
                  <span className={styles.userEmail}>{g.user_email}</span>
                </td>
                <td>{g.org_name}</td>
                <td>
                  <RoleBadge role={g.role} revoked={!!g.revoked_at} />
                </td>
                <td>
                  <span className={styles.dateText}>{formatDate(g.created_at)}</span>
                </td>
                <td>
                  <button
                    className={styles.btnRevoke}
                    disabled={!!g.revoked_at || revokingId === g.id}
                    onClick={() => handleRevoke(g.id)}
                  >
                    {revokingId === g.id ? "…" : "Révoquer"}
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {open && (
        <div className={styles.overlay} onClick={closeDrawer}>
          <div className={styles.drawer} onClick={(e) => e.stopPropagation()}>
            <div className={styles.drawerTitle}>Inviter un utilisateur</div>
            <form onSubmit={handleCreate}>
              <div className={styles.formGroup}>
                <label className={styles.label}>Email *</label>
                <input
                  className={styles.input}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="user@client.com"
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Nom affiché</label>
                <input
                  className={styles.input}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Jean Dupont"
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Organisation *</label>
                <select
                  className={styles.select}
                  value={orgId}
                  onChange={(e) => setOrgId(e.target.value)}
                  required
                >
                  <option value="">Choisir une organisation…</option>
                  {orgs.map((o) => (
                    <option key={o.id} value={o.id}>{o.name}</option>
                  ))}
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Rôle *</label>
                <select
                  className={styles.select}
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                >
                  <option value="client_member">Membre client</option>
                  <option value="reviewer">Reviewer</option>
                  <option value="agency_admin">Admin agence</option>
                </select>
              </div>
              {error && <p className={styles.errorMsg}>{error}</p>}
              <div className={styles.drawerActions}>
                <button type="button" className={styles.btnSecondary} onClick={closeDrawer}>
                  Annuler
                </button>
                <button type="submit" className={styles.btnPrimary} disabled={loading}>
                  {loading ? "Invitation…" : "Inviter"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
