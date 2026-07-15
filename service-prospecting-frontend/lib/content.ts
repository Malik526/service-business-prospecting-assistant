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

