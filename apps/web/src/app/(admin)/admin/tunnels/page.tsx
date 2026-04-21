// Back-office — Inventaire tunnels Cloudflare
import { redirect } from "next/navigation";
import { serverAdminApi, AdminApiError, type DiscoveredTunnelItem, type AdminEnvItem } from "@/lib/api/server-admin";
import { TunnelsClient } from "./TunnelsClient";

export default async function AdminTunnelsPage() {
  let tunnels: DiscoveredTunnelItem[];
  let envs: AdminEnvItem[];

  try {
    [tunnels, envs] = await Promise.all([
      serverAdminApi.discoveredTunnels(),
      serverAdminApi.environments(),
    ]);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    redirect("/session-expired");
  }

  return <TunnelsClient initialTunnels={tunnels} envs={envs} />;
}
