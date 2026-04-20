import type { ReactNode } from "react";
import styles from "./AuthCard.module.css";

interface Props {
  children: ReactNode;
  footer?: ReactNode;
}

export function AuthCard({ children, footer }: Props) {
  return (
    <div className={styles.card}>
      <div className={styles.brand}>
        <div className={styles.logo}>AG</div>
        <div className={styles.name}>
          {process.env.NEXT_PUBLIC_AGENCY_NAME ?? "Agence"}
        </div>
      </div>
      {children}
      {footer && <div className={styles.footer}>{footer}</div>}
    </div>
  );
}
