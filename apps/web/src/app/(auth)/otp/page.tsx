// E03 — Saisie OTP
// Référence visuelle : docs/ds/mockups/devgate-e03-otp.mockup.html
"use client";

import { Suspense } from "react";
import OtpContent from "./OtpContent";

export default function OtpPage() {
  return (
    <Suspense>
      <OtpContent />
    </Suspense>
  );
}
