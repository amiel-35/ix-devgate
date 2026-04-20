// E04 — Portail (accueil post-login)
// Référence visuelle : docs/ds/mockups/devgate-e04-portal.mockup.html
import { redirect } from "next/navigation";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import { PortalDashboard } from "./PortalDashboard";

export default async function PortalPage() {
  let user;
  let environments;

  try {
    [user, environments] = await Promise.all([
      serverPortalApi.me(),
      serverPortalApi.environments(),
    ]);
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    redirect("/session-expired");
  }

  return <PortalDashboard user={user} environments={environments} />;
}
