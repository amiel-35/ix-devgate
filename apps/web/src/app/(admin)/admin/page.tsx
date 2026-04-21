// Back-office — Dashboard
// Référence visuelle : docs/ds/mockups/devgate-backoffice.mockup.html
import { redirect } from "next/navigation";
import {
  serverAdminApi,
  AdminApiError,
  type StatsResponse,
  type AdminAuditEvent,
  type GatewayStats,
} from "@/lib/api/server-admin";
import styles from "./admin.module.css";

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default async function AdminDashboardPage() {
  let stats: StatsResponse;
  let events: AdminAuditEvent[];
  let gatewayStats: GatewayStats;

  try {
    [stats, events, gatewayStats] = await Promise.all([
      serverAdminApi.stats(),
      serverAdminApi.auditEvents(10),
      serverAdminApi.gatewayStats(),
    ]);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    redirect("/session-expired");
  }

  const STATS = [
    { label: "Clients actifs", value: stats.active_orgs },
    { label: "Environnements", value: stats.active_envs },
    { label: "Utilisateurs", value: stats.active_users },
    { label: "Événements aujourd'hui", value: stats.events_today },
  ];

  const GATEWAY_STATS = [
    { label: "Requêtes (24h)", value: gatewayStats.total_requests },
    { label: "Erreurs 5xx", value: gatewayStats.errors_5xx },
    { label: "Refus CF Access", value: gatewayStats.cf_refused },
    { label: "Upstream indispo", value: gatewayStats.upstream_unavailable },
    {
      label: "Latence moy.",
      value: gatewayStats.avg_latency_ms !== null ? `${gatewayStats.avg_latency_ms}ms` : "—",
    },
    {
      label: "Latence p95",
      value: gatewayStats.p95_latency_ms !== null ? `${gatewayStats.p95_latency_ms}ms` : "—",
    },
  ];

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Dashboard</h1>
      <p className={styles.pageSub}>Vue d&apos;ensemble de l&apos;activité DevGate</p>

      <div className={styles.statsGrid}>
        {STATS.map((s) => (
          <div key={s.label} className={styles.statCard}>
            <div className={styles.statLabel}>{s.label}</div>
            <div className={styles.statValue}>{s.value}</div>
          </div>
        ))}
      </div>

      <div className={styles.sectionTitle} style={{ marginTop: "28px", marginBottom: "12px" }}>
        Gateway — 24 dernières heures
      </div>
      <div className={styles.statsGrid}>
        {GATEWAY_STATS.map((s) => (
          <div key={s.label} className={styles.statCard}>
            <div className={styles.statLabel}>{s.label}</div>
            <div className={styles.statValue}>{s.value}</div>
          </div>
        ))}
      </div>

      <div className={styles.sectionTitle} style={{ marginTop: "28px" }}>Activité récente</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Date</th>
            <th>Événement</th>
            <th>Acteur</th>
            <th>Cible</th>
          </tr>
        </thead>
        <tbody>
          {events.length === 0 ? (
            <tr className={styles.emptyRow}>
              <td colSpan={4}>Aucun événement enregistré</td>
            </tr>
          ) : (
            events.map((e) => (
              <tr key={e.id}>
                <td>{formatDate(e.created_at)}</td>
                <td>
                  <span className={styles.eventType}>{e.event_type}</span>
                </td>
                <td>{e.actor_user_id ?? "—"}</td>
                <td>{e.target_id ?? "—"}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
