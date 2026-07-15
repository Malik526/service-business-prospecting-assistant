/** Defines shared request and response types for prospecting API data.
 *  Used by the API client, results table, CSV export, and page state.
 */

export interface Prospect {
  place_id: string;
  business_name: string;
  category: string;
  rating: number;
  review_count: number;
  lead_score: number;
  weighted_reputation_score: number;
  address: string;
  phone: string;
  website: string;
  google_maps_url: string;
  distance_miles: number;
  email?: string;
  instagram_url?: string;
}

export interface SearchRequest {
  zip_code: string;
  radius: number;
  categories?: string;
  user_id?: string;
}

export interface SearchResponse {
  count: number;
  duplicate_count: number;
  prospects: Prospect[];
  search_id: string;
  user_id: string;
}

export interface StoredProspectsResponse {
  count: number;
  prospects: Prospect[];
}

export interface ApiErrorPayload {
  detail?: string;
}

export interface UserProfile {
  id: string;
  email: string;
  created_at?: string;
  free_tier_searches_used: number;
  free_tier_searches_limit: number;
  subscription_status: "free" | "starter" | "pro" | "business";
  stripe_customer_id?: string;
  stripe_subscription_id?: string;
  last_search_date?: string;
  updated_at?: string;
}

export interface CheckoutSessionResponse {
  session_id: string;
  checkout_url: string;
}

export interface BillingPortalResponse {
  portal_url: string;
}

export interface FeedbackResponse {
  status: string;
  feedback_id: string;
}

export interface AdminStats {
  total_users: number;
  free_users: number;
  paid_users: number;
  total_searches: number;
  total_revenue: number;
}
