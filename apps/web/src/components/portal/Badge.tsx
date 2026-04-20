import styles from "./Badge.module.css";

interface KindBadgeProps {
  kind: string; // "staging" | "preview" | "dev" | "internal"
}

export function KindBadge({ kind }: KindBadgeProps) {
  const cls = (styles as Record<string, string>)[kind] ?? styles.internal;
  return (
    <span className={`${styles.badge} ${cls}`}>
      {kind}
    </span>
  );
}

interface StatusBadgeProps {
  status: string; // "online" | "offline" | "unknown"
}

const STATUS_LABELS: Record<string, string> = {
  online: "En ligne",
  offline: "Hors ligne",
  unknown: "Inconnu",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const cls = (styles as Record<string, string>)[status] ?? styles.unknown;
  const label = STATUS_LABELS[status] ?? "Inconnu";
  return (
    <span className={`${styles.badge} ${cls}`}>
      <span className={styles.dot} />
      {label}
    </span>
  );
}

export function AuthBadge() {
  return (
    <span className={`${styles.badge} ${styles.auth}`}>
      🔒 Auth requise
    </span>
  );
}
