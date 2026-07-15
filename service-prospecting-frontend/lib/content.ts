/** Centralizes user-facing copy and selectable categories for the app.
 *  Components import this file instead of hardcoding repeated labels/options.
 */

export const appContent = {
  title: "Service Business Prospecting",
  description: "Find and qualify local service businesses by ZIP code, category, and radius.",
  eyebrow: "Growth agency research",
  tagline: "Discover service businesses, score outreach fit, and export a clean call list.",
  emptyTitle: "Start with a target market",
  emptyBody: "Enter a ZIP code, choose a search radius, and select service categories.",
  noResultsTitle: "No prospects found",
  noResultsBody: "Try a larger radius, fewer categories, or a nearby ZIP code.",
  errorTitle: "Search failed",
  footer: "Service Prospecting v1.0. Data from Google Places.",
  authTitle: "Sign in to Service Prospecting",
  authBody: "Use your account to track searches, save usage history, and manage upgrades.",
  setupTitle: "Supabase setup required",
  setupBody: "Add Supabase project URL and anon key values before enabling authenticated access.",
  usageLabel: "Monthly searches",
  upgradeTitle: "Choose a plan",
  upgradeBody: "Start free, then upgrade when search volume proves useful.",
  feedbackTitle: "Share product feedback",
  feedbackBody: "Tell us what worked, what blocked you, and what would make this worth paying for.",
};

export const categoryOptions = [
  { label: "Electricians", value: "electrician" },
  { label: "Plumbers", value: "plumber" },
  { label: "HVAC", value: "hvac" },
  { label: "Dentists", value: "dentist" },
  { label: "Med spas", value: "med spa" },
  { label: "Caterers", value: "catering" },
  { label: "Contractors", value: "contractor" },
  { label: "Cleaning companies", value: "cleaning company" },
  { label: "Salons", value: "hair salon" },
  { label: "Fitness studios", value: "fitness studio" },
];

export const defaultSearchValues = {
  zipCode: "11385",
  radius: 20,
  categories: "electrician,plumber",
};

export const pricingTiers = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    searches: "25 searches/month",
    priceId: "",
    features: ["25 monthly searches", "Lead scoring", "CSV export", "Google Maps links"],
  },
  {
    name: "Starter",
    price: "$29",
    period: "month",
    searches: "250 searches/month",
    priceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_STARTER_MONTHLY || "price_starter_monthly",
    features: [
      "250 monthly searches",
      "Everything in Free",
      "Priority search capacity",
      "Email support",
    ],
  },
  {
    name: "Pro",
    price: "$79",
    period: "month",
    searches: "1,000 searches/month",
    priceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_PRO_MONTHLY || "price_pro_monthly",
    features: [
      "1,000 monthly searches",
      "Everything in Starter",
      "Phone support",
      "Advanced analytics",
    ],
  },
  {
    name: "Business",
    price: "$199",
    period: "month",
    searches: "5,000 searches/month",
    priceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_BUSINESS_MONTHLY || "price_business_monthly",
    features: [
      "5,000 monthly searches",
      "Everything in Pro",
      "Account support",
      "Custom integrations",
    ],
  },
];
