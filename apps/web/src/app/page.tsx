import { redirect } from "next/navigation";
import { getServerSession } from "@/lib/auth/session";

// Racine → portail si session, sinon login
export default async function RootPage() {
  const session = await getServerSession();
  if (session) redirect("/portal");
  redirect("/login");
}
