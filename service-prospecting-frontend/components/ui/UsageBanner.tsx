/** Usage banner for subscription search limits.
 *  Props: user profile fields determine used/limit progress and upgrade messaging.
 */

import Link from "next/link";

import styles from "../../styles/prospecting.module.css";
import type { UserProfile } from "../../types/prospect";

interface UsageBannerProps {
  profile: UserProfile;
}

/** Shows current plan usage and the upgrade prompt when limits are exhausted. */
export function UsageBanner({ profile }: UsageBannerProps): JSX.Element {
  const used = profile.free_tier_searches_used || 0;
  const limit = profile.free_tier_searches_limit || 25;
  const limitReached = used >= limit;

  return (
    <section className={styles.usageBanner} aria-label="Plan usage">
      <div className={styles.usageCopy}>
        <p className={styles.kicker}>{profile.subscription_status} plan</p>
        <h2>
          {used} of {limit} monthly searches used
        </h2>
      </div>
      <progress className={styles.usageMeter} value={used} max={limit} />
      {limitReached ? (
        <Link className={styles.inlineAction} href="/upgrade">
          Upgrade to continue searching
        </Link>
      ) : null}
    </section>
  );
}
