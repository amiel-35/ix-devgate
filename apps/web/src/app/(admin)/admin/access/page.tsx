// Back-office — Accès (grants)
import { redirect } from "next/navigation";
import {
  serverAdminApi,
  AdminApiError,
  type GrantItem,
  type OrgItem,
} from "@/lib/api/server-admin";
import { AccessClient } from "./AccessClient";

export default async function AdminAccessPage() {
  let grants: GrantItem[];
  let orgs: OrgItem[];

  try {
    [grants, orgs] = await Promise.all([
      serverAdminApi.grants(),
      serverAdminApi.organizations(),
    ]);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    redirect("/session-expired");
  }

  return <AccessClient initialGrants={grants} orgs={orgs} />;
}
