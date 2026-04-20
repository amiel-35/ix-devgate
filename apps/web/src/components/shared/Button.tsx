import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./Button.module.css";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "link";
  children: ReactNode;
}

export function Button({ variant = "primary", className, children, ...rest }: Props) {
  const cls = [styles.btn, styles[variant], className].filter(Boolean).join(" ");
  return (
    <button className={cls} {...rest}>
      {children}
    </button>
  );
}
