/** Admin dashboard metric card.
 *  Props: label and value render one compact metric panel.
 */

import styles from "../../styles/prospecting.module.css";

interface AdminStatCardProps {
  label: string;
  value: number | string;
}

/** Renders one admin metric for the dashboard grid. */
export function AdminStatCard({ label, value }: AdminStatCardProps): JSX.Element {
  return (
    <article className={styles.statCard}>
      <p>{label}</p>
      <strong>{value}</strong>
    </article>
  );
}

