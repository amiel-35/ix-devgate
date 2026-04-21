"use client";

import { useState } from "react";
import type { DiscoveredTunnelItem, AdminEnvItem } from "@/lib/api/server-admin";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

async function apiPost(path: string, body?: object) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText);
  return res.json();
}

const STATUS_LABEL: Record<string, string> = {
  discovered: "Découvert",
  assigned: "Assigné",
  orphaned: "Orphelin",
};

const STATUS_COLOR: Record<string, string> = {
  discovered: "#2563eb",
  assigned: "#16a34a",
  orphaned: "#dc2626",
};

export function TunnelsClient({
  initialTunnels,
  envs,
}: {
  initialTunnels: DiscoveredTunnelItem[];
  envs: AdminEnvItem[];
}) {
  const [tunnels, setTunnels] = useState(initialTunnels);
  const [message, setMessage] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [selectedEnv, setSelectedEnv] = useState<Record<string, string>>({});

  async function handleSync() {
    setSyncing(true);
    setMessage("");
    try {
      const result = await apiPost("/admin/sync-tunnels");
      if (result.error) {
        setMessage(`Erreur sync CF: ${result.error}`);
      } else {
        setMessage(`Sync OK — ${result.discovered} nouveaux, ${result.updated} mis à jour, ${result.orphaned} orphelins`);
        const updated = await fetch(`${API_BASE}/admin/discovered-tunnels`, { credentials: "include" });
        if (updated.ok) setTunnels(await updated.json());
      }
    } catch (e: unknown) {
      setMessage(`Erreur: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSyncing(false);
    }
  }

  async function handleAssign(tunnelId: string) {
    const envId = selectedEnv[tunnelId];
    if (!envId) { setMessage("Sélectionnez un environnement d'abord"); return; }
    try {
      await apiPost(`/admin/discovered-tunnels/${tunnelId}/assign`, { environment_id: envId });
      setMessage("Tunnel assigné avec succès");
      setTunnels((prev) =>
        prev.map((t) => (t.id === tunnelId ? { ...t, status: "assigned" } : t))
      );
    } catch (e: unknown) {
      setMessage(`Erreur: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  async function handleActivate(envId: string) {
    setMessage("Provisioning en cours…");
    try {
      const result = await apiPost(`/admin/environments/${envId}/activate`);
      if (result.error) {
        setMessage(`Provisioning échoué (${result.state}): ${result.error}`);
      } else {
        setMessage(`Environnement activé (job: ${result.job_id})`);
      }
    } catch (e: unknown) {
      setMessage(`Erreur: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700 }}>Tunnels Cloudflare</h1>
        <button
          onClick={handleSync}
          disabled={syncing}
          style={{ padding: "0.5rem 1rem", background: syncing ? "#9ca3af" : "#1d4ed8", color: "#fff", border: "none", borderRadius: "6px", cursor: syncing ? "not-allowed" : "pointer" }}
        >
          {syncing ? "Sync…" : "Sync maintenant"}
        </button>
      </div>

      {message && (
        <div style={{ background: "#f0f9ff", border: "1px solid #bae6fd", borderRadius: "6px", padding: "0.75rem 1rem", marginBottom: "1rem", color: "#0369a1" }}>
          {message}
        </div>
      )}

      {tunnels.length === 0 ? (
        <p style={{ color: "#6b7280" }}>Aucun tunnel découvert. Cliquez sur "Sync maintenant" pour interroger Cloudflare.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left" }}>
              <th style={{ padding: "0.75rem 1rem" }}>Nom CF</th>
              <th style={{ padding: "0.75rem 1rem" }}>ID Tunnel</th>
              <th style={{ padding: "0.75rem 1rem" }}>Statut</th>
              <th style={{ padding: "0.75rem 1rem" }}>Vu pour la dernière fois</th>
              <th style={{ padding: "0.75rem 1rem" }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {tunnels.map((t) => (
              <tr key={t.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: "0.75rem 1rem", fontWeight: 500 }}>{t.name}</td>
                <td style={{ padding: "0.75rem 1rem", fontFamily: "monospace", fontSize: "0.85em", color: "#6b7280" }}>
                  {t.cloudflare_tunnel_id.slice(0, 8)}…
                </td>
                <td style={{ padding: "0.75rem 1rem" }}>
                  <span style={{ background: STATUS_COLOR[t.status] + "22", color: STATUS_COLOR[t.status], padding: "0.2rem 0.6rem", borderRadius: "999px", fontSize: "0.85em", fontWeight: 600 }}>
                    {STATUS_LABEL[t.status] ?? t.status}
                  </span>
                </td>
                <td style={{ padding: "0.75rem 1rem", color: "#6b7280", fontSize: "0.9em" }}>
                  {t.last_seen_at ? new Date(t.last_seen_at).toLocaleString("fr-FR") : "—"}
                </td>
                <td style={{ padding: "0.75rem 1rem" }}>
                  {t.status === "discovered" && (
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <select
                        value={selectedEnv[t.id] ?? ""}
                        onChange={(e) => setSelectedEnv((p) => ({ ...p, [t.id]: e.target.value }))}
                        style={{ padding: "0.4rem", border: "1px solid #d1d5db", borderRadius: "4px", fontSize: "0.9em" }}
                      >
                        <option value="">— Environnement —</option>
                        {envs.map((e) => (
                          <option key={e.id} value={e.id}>{e.org_name} / {e.name}</option>
                        ))}
                      </select>
                      <button
                        onClick={() => handleAssign(t.id)}
                        style={{ padding: "0.4rem 0.8rem", background: "#1d4ed8", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "0.9em" }}
                      >
                        Affecter
                      </button>
                    </div>
                  )}
                  {t.status === "assigned" && (
                    <button
                      onClick={() => {
                        const envId = selectedEnv[t.id];
                        if (envId) {
                          handleActivate(envId);
                        } else {
                          setMessage("Sélectionnez l'environnement lié pour activer");
                        }
                      }}
                      style={{ padding: "0.4rem 0.8rem", background: "#16a34a", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "0.9em" }}
                    >
                      Activer
                    </button>
                  )}
                  {t.status === "orphaned" && (
                    <span style={{ color: "#dc2626", fontSize: "0.9em" }}>Orphelin — vérifier CF</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
