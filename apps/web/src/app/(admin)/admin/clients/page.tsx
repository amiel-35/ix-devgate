// Back-office — Clients (organisations)
import { redirect } from "next/navigation";
import { serverAdminApi, AdminApiError } from "@/lib/api/server-admin";
import { ClientsClient } from "./ClientsClient";

export default async function AdminClientsPage() {
  let orgs;
  let projects;

  try {
    [orgs, projects] = await Promise.all([
      serverAdminApi.organizations(),
      serverAdminApi.projects(),
    ]);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    redirect("/session-expired");
  }

  return <ClientsClient initialOrgs={orgs} initialProjects={projects} />;
}
