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
