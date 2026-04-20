"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, portalApi } from "@/lib/api/client";
import type { MeResponse, SessionItem } from "@/lib/api/server";
import styles from "./profile.module.css";

interface Props {
  user: MeResponse;
  initialSessions: SessionItem[];
}

function initials(user: MeResponse): string {
  const name = user.display_name ?? user.email;
  return name
    .split(/[\s@]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function daysUntil(iso: string): number {
  const ms = new Date(iso).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / 86_400_000));
}

export function ProfileClient({ user, initialSessions }: Props) {
  const router = useRouter();
  const [sessions, setSessions] = useState(initialSessions);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState(user.display_name ?? "");

  async function handleRevoke(sessionId: string) {
    setRevokingId(sessionId);
    try {
      await portalApi.revokeSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } finally {
      setRevokingId(null);
    }
  }

  async function handleLogout() {
    await authApi.logout();
    router.push("/login");
  }

  return (
    <div className={styles.main}>
      <h1 className={styles.pageTitle}>Mon profil</h1>
      <p className={styles.pageSub}>Informations personnelles et sessions actives</p>

      <div className={styles.layout}>
        {/* Carte profil */}
        <div>
          <div className={styles.profileCard}>
            <div className={styles.avatarLg}>{initials(user)}</div>
            <div className={styles.profileName}>{user.display_name ?? user.email.split("@")[0]}</div>
            <div className={styles.profileEmail}>{user.email}</div>
            <span className={styles.roleBadge}>client_member</span>

            <div className={styles.divider} />

            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>Nom affiché</label>
              <input
                className={styles.fieldInput}
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Votre nom"
              />
            </div>
            <button className={styles.btnPrimary} type="button">
              Mettre à jour
            </button>
            <button className={styles.btnDanger} type="button" onClick={handleLogout}>
              Se déconnecter
            </button>
          </div>
        </div>

        {/* Sessions actives */}
        <div>
          <div className={styles.sectionTitle}>Sessions actives</div>
          <div className={styles.sessions}>
            {sessions.map((s) => (
              <div
                key={s.id}
                className={`${styles.session} ${s.is_current ? styles.sessionCurrent : ""}`}
                data-current={s.is_current}
              >
                <div>
                  {s.is_current && <div className={styles.curLabel}>Session actuelle</div>}
                  <div className={styles.sessionDevice}>
                    {s.user_agent ?? "Appareil inconnu"}
                  </div>
                  <div className={styles.sessionMeta}>
                    {s.ip ? `IP ${s.ip} · ` : ""}
                    Créée le {formatDate(s.last_seen_at)} · Expire dans {daysUntil(s.expires_at)} jour
                    {daysUntil(s.expires_at) !== 1 ? "s" : ""}
                  </div>
                </div>
                <button
                  className={styles.btnRevoke}
                  type="button"
                  disabled={s.is_current || revokingId === s.id}
                  onClick={() => handleRevoke(s.id)}
                >
                  {revokingId === s.id ? "…" : "Révoquer"}
                </button>
              </div>
            ))}
          </div>
          <div className={styles.notice}>
            ℹ️ Chaque session est valide 7 jours. La révocation est immédiate.
          </div>
        </div>
      </div>
    </div>
  );
}
