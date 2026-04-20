// Layout back-office agence
// Vérifie la session + rôle agency_admin côté backend
import { requireAdminSession } from "@/lib/auth/session";
import type { ReactNode } from "react";

export default async function AdminLayout({ children }: { children: ReactNode }) {
  await requireAdminSession();
  return (
    <div>
      {/* TODO: AdminSidebar (Dashboard, Clients, Environnements, Accès, Audit) */}
      <main>{children}</main>
    </div>
  );
}
