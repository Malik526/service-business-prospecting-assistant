/** Pricing card for upgrade tiers.
 *  Props: tier content, current plan name, and checkout handler.
 */

import { Check } from "lucide-react";

import styles from "../../styles/prospecting.module.css";

interface PricingTier {
  name: string;
  price: string;
  period: string;
  searches: string;
  priceId: string;
  features: string[];
}

interface PricingCardProps {
  tier: PricingTier;
  currentPlan: string;
  loading: boolean;
  onSelect: (priceId: string) => void;
}

/** Renders one subscription plan with upgrade action. */
export function PricingCard({
  tier,
  currentPlan,
  loading,
  onSelect,
}: PricingCardProps): JSX.Element {
  const isCurrent = tier.name.toLowerCase() === currentPlan;

  return (
    <article className={styles.pricingCard}>
      <p className={styles.kicker}>{tier.searches}</p>
      <h2>{tier.name}</h2>
      <p className={styles.priceLine}>
        <span>{tier.price}</span> {tier.period}
      </p>
      <button
        className={styles.searchButton}
        type="button"
        disabled={loading || isCurrent}
        onClick={() => onSelect(tier.priceId)}
      >
        {isCurrent ? "Current plan" : "Select plan"}
      </button>
      <ul className={styles.featureList}>
        {tier.features.map((feature) => (
          <li key={feature}>
            <Check aria-hidden="true" size={16} />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

