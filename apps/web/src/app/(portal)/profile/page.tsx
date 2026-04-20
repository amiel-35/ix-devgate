// E12 — Profil / sessions actives
// Référence visuelle : docs/ds/mockups/devgate-e12-profile.mockup.html
import { redirect } from "next/navigation";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import { ProfileClient } from "./ProfileClient";

export default async function ProfilePage() {
  let user;
  let sessions;

  try {
    [user, sessions] = await Promise.all([
      serverPortalApi.me(),
      serverPortalApi.sessions(),
    ]);
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    redirect("/session-expired");
  }

  return <ProfileClient user={user} initialSessions={sessions} />;
}
