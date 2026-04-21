// Layout back-office agence
// Vérifie la session + rôle agency_admin côté backend (403 → /access-denied)
import { redirect } from "next/navigation";
import { requireAdminSession } from "@/lib/auth/session";
import { serverAdminApi, AdminApiError } from "@/lib/api/server-admin";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import type { ReactNode } from "react";

export default async function AdminLayout({ children }: { children: ReactNode }) {
  await requireAdminSession();

  // Vérification du rôle : si 403, l'utilisateur n'est pas agency_admin
  try {
    await serverAdminApi.stats();
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    // Tout autre cas (401, 500, timeout) : refuser l'accès
    redirect("/login");
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--color-bg)" }}>
      <AdminSidebar />
      <main style={{ flex: 1, overflow: "auto" }}>{children}</main>
    </div>
  );
}
