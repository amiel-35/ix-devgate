"use client";

import { useState } from "react";
import { adminApi, AdminCreateOrgPayload, AdminCreateProjectPayload } from "@/lib/api/client";
import type { OrgItem, ProjectItem } from "@/lib/api/server-admin";
import styles from "./clients.module.css";

interface Props {
  initialOrgs: OrgItem[];
  initialProjects: ProjectItem[];
}

type Modal = null | "create-org" | "create-project";

export function ClientsClient({ initialOrgs, initialProjects }: Props) {
  const [orgs, setOrgs] = useState(initialOrgs);
  const [projects, setProjects] = useState(initialProjects);
  const [modal, setModal] = useState<Modal>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Formulaire org
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [orgEmail, setOrgEmail] = useState("");

  // Formulaire projet
  const [projOrgId, setProjOrgId] = useState("");
  const [projName, setProjName] = useState("");
  const [projSlug, setProjSlug] = useState("");

  function openModal(m: Modal) {
    setError(null);
    setModal(m);
  }

  function closeModal() {
    setModal(null);
    setError(null);
    setOrgName(""); setOrgSlug(""); setOrgEmail("");
    setProjOrgId(""); setProjName(""); setProjSlug("");
  }

  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload: AdminCreateOrgPayload = {
        name: orgName,
        slug: orgSlug,
        support_email: orgEmail || undefined,
      };
      await adminApi.organizations.create(payload);
      const updated = await adminApi.organizations.list() as OrgItem[];
      setOrgs(updated);
      closeModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateProject(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload: AdminCreateProjectPayload = {
        organization_id: projOrgId,
        name: projName,
        slug: projSlug,
      };
      await adminApi.projects.create(payload);
      const updated = await adminApi.projects.list() as ProjectItem[];
      setProjects(updated);
      closeModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  const projCountByOrg = projects.reduce<Record<string, number>>((acc, p) => {
    acc[p.organization_id] = (acc[p.organization_id] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Clients</h1>
      <p className={styles.pageSub}>Organisations rattachées à DevGate</p>

      <div className={styles.toolbar}>
        <span className={styles.sectionTitle}>
          {orgs.length} client{orgs.length !== 1 ? "s" : ""}
        </span>
        <div style={{ display: "flex", gap: "8px" }}>
          <button className={styles.btnSecondary} onClick={() => openModal("create-project")}>
            + Nouveau projet
          </button>
          <button className={styles.btnPrimary} onClick={() => openModal("create-org")}>
            + Nouveau client
          </button>
        </div>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Client</th>
            <th>Slug</th>
            <th>Projets</th>
            <th>Environnements</th>
            <th>Utilisateurs actifs</th>
          </tr>
        </thead>
        <tbody>
          {orgs.length === 0 ? (
            <tr className={styles.emptyRow}>
              <td colSpan={5}>Aucun client — créez le premier</td>
            </tr>
          ) : (
            orgs.map((org) => (
              <tr key={org.id}>
                <td>
                  <div className={styles.orgName}>{org.name}</div>
                  {org.support_email && (
                    <div className={styles.orgSlug}>{org.support_email}</div>
                  )}
                </td>
                <td><span className={styles.orgSlug}>{org.slug}</span></td>
                <td><span className={styles.count}>{projCountByOrg[org.id] ?? 0}</span></td>
                <td><span className={styles.count}>{org.env_count}</span></td>
                <td><span className={styles.count}>{org.user_count}</span></td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Modal créer org */}
      {modal === "create-org" && (
        <div className={styles.overlay} onClick={closeModal}>
          <div className={styles.drawer} onClick={(e) => e.stopPropagation()}>
            <div className={styles.drawerTitle}>Nouveau client</div>
            <form onSubmit={handleCreateOrg}>
              <div className={styles.formGroup}>
                <label className={styles.label}>Nom du client *</label>
                <input
                  className={styles.input}
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  required
                  placeholder="Ex: Acme Corp"
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Slug (identifiant URL) *</label>
                <input
                  className={styles.input}
                  value={orgSlug}
                  onChange={(e) => setOrgSlug(e.target.value)}
                  required
                  placeholder="acme-corp"
                  pattern="[a-z0-9\-]+"
                  title="Minuscules, chiffres et tirets uniquement"
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Email support</label>
                <input
                  className={styles.input}
                  type="email"
                  value={orgEmail}
                  onChange={(e) => setOrgEmail(e.target.value)}
                  placeholder="support@acme.com"
                />
              </div>
              {error && <p className={styles.errorMsg}>{error}</p>}
              <div className={styles.drawerActions}>
                <button type="button" className={styles.btnSecondary} onClick={closeModal}>
                  Annuler
                </button>
                <button type="submit" className={styles.btnPrimary} disabled={loading}>
                  {loading ? "Création…" : "Créer le client"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal créer projet */}
      {modal === "create-project" && (
        <div className={styles.overlay} onClick={closeModal}>
          <div className={styles.drawer} onClick={(e) => e.stopPropagation()}>
            <div className={styles.drawerTitle}>Nouveau projet</div>
            <form onSubmit={handleCreateProject}>
              <div className={styles.formGroup}>
                <label className={styles.label}>Client *</label>
                <select
                  className={styles.select}
                  value={projOrgId}
                  onChange={(e) => setProjOrgId(e.target.value)}
                  required
                >
                  <option value="">Choisir un client…</option>
                  {orgs.map((o) => (
                    <option key={o.id} value={o.id}>{o.name}</option>
                  ))}
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Nom du projet *</label>
                <input
                  className={styles.input}
                  value={projName}
                  onChange={(e) => setProjName(e.target.value)}
                  required
                  placeholder="Ex: Refonte site"
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Slug *</label>
                <input
                  className={styles.input}
                  value={projSlug}
                  onChange={(e) => setProjSlug(e.target.value)}
                  required
                  placeholder="refonte-site"
                  pattern="[a-z0-9\-]+"
                />
              </div>
              {error && <p className={styles.errorMsg}>{error}</p>}
              <div className={styles.drawerActions}>
                <button type="button" className={styles.btnSecondary} onClick={closeModal}>
                  Annuler
                </button>
                <button type="submit" className={styles.btnPrimary} disabled={loading}>
                  {loading ? "Création…" : "Créer le projet"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
