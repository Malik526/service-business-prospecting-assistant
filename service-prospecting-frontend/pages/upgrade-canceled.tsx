/** Stripe checkout cancellation page.
 *  Gives users a clean path back to pricing after canceling Checkout.
 */

import Link from "next/link";

import styles from "../styles/prospecting.module.css";

/** Renders a checkout cancellation message. */
export default function UpgradeCanceledPage(): JSX.Element {
  return (
    <main className={styles.centeredPage}>
      <section className={styles.authPanel}>
        <p className={styles.kicker}>Checkout canceled</p>
        <h1>No plan changes were made</h1>
        <p>You can keep using the free tier or choose a paid plan whenever you are ready.</p>
        <Link className={styles.inlineAction} href="/upgrade">
          View plans
        </Link>
      </section>
    </main>
  );
}

