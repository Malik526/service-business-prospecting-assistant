/** Stripe checkout success page.
 *  Sends users back to the prospecting workspace after a successful upgrade.
 */

import Link from "next/link";

import styles from "../styles/prospecting.module.css";

/** Renders a simple checkout success confirmation. */
export default function UpgradeSuccessPage(): JSX.Element {
  return (
    <main className={styles.centeredPage}>
      <section className={styles.authPanel}>
        <p className={styles.kicker}>Upgrade complete</p>
        <h1>Your plan is active</h1>
        <p>Stripe confirmed checkout. Your account will reflect the new limit after webhook sync.</p>
        <Link className={styles.inlineAction} href="/prospecting">
          Return to prospecting
        </Link>
      </section>
    </main>
  );
}

