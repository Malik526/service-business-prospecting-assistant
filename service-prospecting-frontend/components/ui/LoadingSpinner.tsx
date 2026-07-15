/** Loading indicator for long-running prospect searches.
 *  This component accepts no props and uses CSS module animation for styling.
 */

import { LoaderCircle } from "lucide-react";

import styles from "../../styles/prospecting.module.css";

/** Renders an accessible loading state while the API request is in flight. */
export function LoadingSpinner(): JSX.Element {
  return (
    <div className={styles.loadingState} role="status" aria-live="polite">
      <LoaderCircle aria-hidden="true" size={28} />
      <span>Searching Google Places and scoring prospects</span>
    </div>
  );
}

