// Layout portail — vérifie la session, affiche le header brandé agence
import { requireSession } from "@/lib/auth/session";
import type { ReactNode } from "react";

export default async function PortalLayout({ children }: { children: ReactNode }) {
  await requireSession();
  // TODO: récupérer le profil utilisateur et injecter dans le contexte
  return (
    <div>
      {/* TODO: PortalHeader (branding agence, user pill, logout) */}
      <main>{children}</main>
    </div>
  );
}
