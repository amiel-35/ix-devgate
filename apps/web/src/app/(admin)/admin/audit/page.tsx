// Back-office — Audit log
import { redirect } from "next/navigation";
import {
  serverAdminApi,
  AdminApiError,
  type AdminAuditEvent,
} from "@/lib/api/server-admin";
import { AuditClient } from "./AuditClient";

export default async function AdminAuditPage() {
  let events: AdminAuditEvent[];

  try {
    events = await serverAdminApi.auditEvents(100);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403)
      redirect("/access-denied");
    redirect("/session-expired");
  }

  return <AuditClient initialEvents={events} />;
}
