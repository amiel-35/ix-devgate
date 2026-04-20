import type { ReactNode } from "react";
import styles from "./StateCard.module.css";

interface Props {
  icon: ReactNode;
  tone: "ok" | "warn" | "danger" | "info";
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
}

export function StateCard({ icon, tone, title, description, children, footer }: Props) {
  return (
    <div className={styles.card}>
      <div className={`${styles.icon} ${styles[tone]}`}>{icon}</div>
      <h1 className={styles.title}>{title}</h1>
      {description && <p className={styles.desc}>{description}</p>}
      {children && <div className={styles.body}>{children}</div>}
      {footer && <p className={styles.footer}>{footer}</p>}
    </div>
  );
}
