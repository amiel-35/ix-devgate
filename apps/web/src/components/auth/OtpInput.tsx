"use client";

import { useRef, useEffect } from "react";
import styles from "./OtpInput.module.css";

interface Props {
  value: string;
  onChange: (val: string) => void;
  length?: number;
}

export function OtpInput({ value, onChange, length = 6 }: Props) {
  const refs = useRef<Array<HTMLInputElement | null>>([]);

  useEffect(() => {
    if (value.length < length) {
      refs.current[value.length]?.focus();
    }
  }, [value, length]);

  function handleChange(i: number, char: string) {
    const digit = char.replace(/\D/g, "").slice(0, 1);
    if (!digit && char !== "") return;
    const next = value.substring(0, i) + digit + value.substring(i + 1);
    onChange(next.slice(0, length));
  }

  function handleKeyDown(i: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !value[i] && i > 0) {
      refs.current[i - 1]?.focus();
    }
  }

  return (
    <div className={styles.group}>
      {Array.from({ length }).map((_, i) => (
        <input
          key={i}
          type="text"
          inputMode="numeric"
          role="textbox"
          maxLength={1}
          className={`${styles.input} ${value[i] ? styles.filled : ""}`}
          value={value[i] ?? ""}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          ref={(el) => { refs.current[i] = el; }}
          aria-label={`Chiffre ${i + 1}`}
        />
      ))}
    </div>
  );
}
