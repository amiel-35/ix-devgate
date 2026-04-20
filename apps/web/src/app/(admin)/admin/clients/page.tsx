// Back-office — Clients (organisations)
import { redirect } from "next/navigation";
import { serverAdminApi, AdminApiError, type OrgItem, type ProjectItem } from "@/lib/api/server-admin";
import { ClientsClient } from "./ClientsClient";

export default async function AdminClientsPage() {
  let orgs: OrgItem[];
  let projects: ProjectItem[];

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
