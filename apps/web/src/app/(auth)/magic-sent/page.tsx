// E02 — Magic link envoyé
// Référence visuelle : docs/ds/mockups/devgate-e02-magic-sent.mockup.html
import { Suspense } from "react";
import MagicSentContent from "./MagicSentContent";

export default function MagicSentPage() {
  return (
    <Suspense>
      <MagicSentContent />
    </Suspense>
  );
}
