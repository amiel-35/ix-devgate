import Link from "next/link";
import { KindBadge, StatusBadge, AuthBadge } from "./Badge";
import type { EnvironmentItem } from "@/lib/api/server";
import styles from "./EnvCard.module.css";

interface Props {
  env: EnvironmentItem;
}

export function EnvCard({ env }: Props) {
  // Extrait juste le hostname pour l'affichage (sans https://)
  const hostname = env.url.replace(/^https?:\/\//, "");

  return (
    <Link href={`/resource/${env.id}`} className={styles.card}>
      <div className={styles.top}>
        <div>
          <div className={styles.org}>{env.organization_name}</div>
          <div className={styles.project}>{env.project_name}</div>
          <div className={styles.envName}>{env.environment_name}</div>
        </div>
        <KindBadge kind={env.kind} />
      </div>

      <div className={styles.meta}>
        <StatusBadge status={env.status} />
        {env.requires_app_auth && <AuthBadge />}
      </div>

      <div className={styles.footer}>
        <span className={styles.hostname}>{hostname}</span>
        {env.status === "offline" ? (
          <span className={styles.disabled}>Indisponible</span>
        ) : (
          <span className={styles.accessBtn}>Accéder ↗</span>
        )}
      </div>
    </Link>
  );
}
