// Back-office — Environnements
import { redirect } from "next/navigation";
import { serverAdminApi, AdminApiError, type AdminEnvItem, type OrgItem, type ProjectItem } from "@/lib/api/server-admin";
import { EnvironmentsClient } from "./EnvironmentsClient";

export default async function AdminEnvironmentsPage() {
  let envs: AdminEnvItem[];
  let orgs: OrgItem[];
  let projects: ProjectItem[];

  try {
    [envs, orgs, projects] = await Promise.all([
      serverAdminApi.environments(),
      serverAdminApi.organizations(),
      serverAdminApi.projects(),
    ]);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    redirect("/session-expired");
  }

  return <EnvironmentsClient initialEnvs={envs} orgs={orgs} initialProjects={projects} />;
}
