// Helpers de session côté serveur (Server Components / middleware)
// Ne jamais utiliser côté client directement

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export const SESSION_COOKIE = "devgate_session";

export async function getServerSession() {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get(SESSION_COOKIE)?.value;
  if (!sessionId) return null;
  return { sessionId };
}

export async function requireSession() {
  const session = await getServerSession();
  if (!session) redirect("/login");
  return session;
}

export async function requireAdminSession() {
  const session = await getServerSession();
  if (!session) redirect("/login");
  // La vérification du rôle agency_admin est faite par le backend
  // Le frontend ne déduit pas les permissions
  return session;
}
