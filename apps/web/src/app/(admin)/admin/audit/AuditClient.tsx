"use client";

import { useState, useMemo } from "react";
import type { AdminAuditEvent } from "@/lib/api/server-admin";
import styles from "./audit.module.css";

interface Props {
  initialEvents: AdminAuditEvent[];
}

const FILTERS = [
  { label: "Tous", value: "" },
  { label: "Auth", value: "auth" },
  { label: "Admin", value: "admin" },
  { label: "Gateway", value: "gateway" },
];

function rowClass(eventType: string): string {
  if (eventType.startsWith("auth.")) return styles.catAuth;
  if (eventType.startsWith("admin.")) return styles.catAdmin;
  if (eventType.startsWith("gateway.")) return styles.catGateway;
  return "";
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AuditClient({ initialEvents }: Props) {
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    if (!filter) return initialEvents;
    return initialEvents.filter((e) => e.event_type.startsWith(filter + "."));
  }, [initialEvents, filter]);

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Audit log</h1>
      <p className={styles.pageSub}>Traçabilité des actions sur DevGate</p>

      <div className={styles.toolbar}>
        <span className={styles.filterLabel}>Catégorie :</span>
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            style={{
              padding: "4px 12px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--color-border)",
              background:
                filter === f.value
                  ? "var(--color-primary)"
                  : "var(--color-surface)",
              color: filter === f.value ? "#fff" : "var(--color-text)",
              fontSize: "12px",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

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
          {filtered.length === 0 ? (
            <tr className={styles.emptyRow}>
              <td colSpan={4}>
                Aucun événement
                {filter ? ` pour la catégorie "${filter}"` : ""}
              </td>
            </tr>
          ) : (
            filtered.map((e) => (
              <tr key={e.id} className={rowClass(e.event_type)}>
                <td>
                  <span className={styles.dateText}>
                    {formatDate(e.created_at)}
                  </span>
                </td>
                <td>
                  <span className={styles.eventType}>{e.event_type}</span>
                </td>
                <td>
                  <span className={styles.actorText}>
                    {e.actor_user_id ?? "système"}
                  </span>
                </td>
                <td>
                  {e.target_id ? (
                    <span className={styles.actorText}>
                      {e.target_type} · {e.target_id.slice(0, 8)}…
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      {filtered.length > 0 && (
        <p className={styles.countNote}>
          {filtered.length} événement{filtered.length !== 1 ? "s" : ""}{" "}
          affiché{filtered.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
