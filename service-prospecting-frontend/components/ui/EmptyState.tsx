/** Empty state component for first-run and no-result moments.
 *  Props: title and body copy explain the current state without extra controls.
 */

import { SearchX } from "lucide-react";

import styles from "../../styles/prospecting.module.css";

interface EmptyStateProps {
  title: string;
  body: string;
}

/** Renders a calm empty-state panel for the prospecting workspace. */
export function EmptyState({ title, body }: EmptyStateProps): JSX.Element {
  return (
    <section className={styles.emptyState} aria-live="polite">
      <SearchX aria-hidden="true" size={28} />
      <h2>{title}</h2>
      <p>{body}</p>
    </section>
  );
}

