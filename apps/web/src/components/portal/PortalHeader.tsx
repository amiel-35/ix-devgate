// Server Component — reçoit les données user en props depuis le layout.
import Link from "next/link";
import type { MeResponse } from "@/lib/api/server";
import { LogoutButton } from "./LogoutButton";
import styles from "./PortalHeader.module.css";

interface Props {
  user: MeResponse;
}

function initials(user: MeResponse): string {
  const name = user.display_name ?? user.email;
  return name
    .split(/[\s@]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

export function PortalHeader({ user }: Props) {
  const displayName = user.display_name ?? user.email.split("@")[0];

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <div className={styles.logo}>AG</div>
        <span className={styles.brandName}>Agence</span>
        <div className={styles.sep} />
        <span className={styles.portalLabel}>DevGate</span>
      </div>
      <div className={styles.userRow}>
        <div className={styles.avatar}>{initials(user)}</div>
        <span className={styles.userName}>{displayName}</span>
        <Link href="/profile" className={styles.ghostBtn}>
          Mon profil
        </Link>
        <LogoutButton />
      </div>
    </header>
  );
}
