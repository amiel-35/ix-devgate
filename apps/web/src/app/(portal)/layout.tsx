// Layout portail — vérifie la session, charge le user, affiche le header brandé agence
import { redirect } from "next/navigation";
import { requireSession } from "@/lib/auth/session";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import { PortalHeader } from "@/components/portal/PortalHeader";
import type { ReactNode } from "react";

export default async function PortalLayout({ children }: { children: ReactNode }) {
  await requireSession();

  let user;
  try {
    user = await serverPortalApi.me();
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    redirect("/session-expired");
  }

  return (
    <div>
      <PortalHeader user={user} />
      <main>{children}</main>
    </div>
  );
}
