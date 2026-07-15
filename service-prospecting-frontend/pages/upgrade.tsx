/** Upgrade page for subscription plan selection.
 *  Uses Stripe Checkout endpoint from the backend and Supabase auth state.
 */

import Head from "next/head";
import { useRouter } from "next/router";
import { useState } from "react";

import { Alert, EmptyState, LoadingSpinner, PricingCard } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { createBillingPortal, createCheckoutSession } from "../lib/api";
import { appContent, pricingTiers } from "../lib/content";
import styles from "../styles/prospecting.module.css";

/** Renders pricing tiers and checkout actions. */
export default function UpgradePage(): JSX.Element {
  const router = useRouter();
  const { authLoading, user, profile, configured } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  /** Starts Stripe Checkout for paid tiers or returns free users to the app. */
  async function handleSelect(priceId: string): Promise<void> {
    if (!user) {
      await router.push("/auth");
      return;
    }

    if (!priceId) {
      await router.push("/prospecting");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const session = await createCheckoutSession(user.id, priceId);
      window.location.href = session.checkout_url;
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not start checkout");
      setLoading(false);
    }
  }

  /** Opens Stripe Billing Portal for users with existing billing details. */
  async function handleManageBilling(): Promise<void> {
    if (!user) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const session = await createBillingPortal(user.id);
      window.location.href = session.portal_url;
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not open billing portal");
      setLoading(false);
    }
  }

  return (
    <>
      <Head>
        <title>{appContent.upgradeTitle}</title>
      </Head>
      <main className={styles.main}>
        {authLoading ? <LoadingSpinner /> : null}
        {!authLoading && !configured ? (
          <EmptyState title={appContent.setupTitle} body={appContent.setupBody} />
        ) : null}
        {!authLoading && configured && user && profile ? (
          <>
            <section className={styles.pageIntro}>
              <p className={styles.kicker}>Pricing</p>
              <h1>{appContent.upgradeTitle}</h1>
              <p>{appContent.upgradeBody}</p>
              <button className={styles.secondaryButton} type="button" onClick={handleManageBilling}>
                Manage billing
              </button>
            </section>
            {error ? <Alert title="Billing error" message={error} /> : null}
            <section className={styles.pricingGrid} aria-label="Pricing plans">
              {pricingTiers.map((tier) => (
                <PricingCard
                  key={tier.name}
                  tier={tier}
                  currentPlan={profile.subscription_status}
                  loading={loading}
                  onSelect={handleSelect}
                />
              ))}
            </section>
          </>
        ) : null}
      </main>
    </>
  );
}

