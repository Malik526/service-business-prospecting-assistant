/** Provides typed HTTP helpers for the prospecting backend API.
 *  All API calls route through this file so base URL and error handling stay consistent.
 */

import axios, { AxiosError } from "axios";

import type {
  ApiErrorPayload,
  AdminStats,
  BillingPortalResponse,
  CheckoutSessionResponse,
  FeedbackResponse,
  SearchRequest,
  SearchResponse,
  StoredProspectsResponse,
} from "../types/prospect";

const API_BASE_URL = process.env.NEXT_PUBLIC_LAMBDA_URL || "http://localhost:8000";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

/** Extracts a readable message from Axios errors returned by the backend. */
function getErrorMessage(error: unknown, fallback: string): string {
  const axiosError = error as AxiosError<ApiErrorPayload>;
  return axiosError.response?.data?.detail || axiosError.message || fallback;
}

/** Searches for prospects using ZIP, radius, categories, and optional user ID. */
export async function searchProspects(request: SearchRequest): Promise<SearchResponse> {
  try {
    const response = await apiClient.post<SearchResponse>("/api/prospects", request);
    return response.data;
  } catch (error) {
    throw new Error(getErrorMessage(error, "Failed to search prospects"));
  }
}

/** Retrieves stored prospects for a user from the backend. */
export async function getUserProspects(
  userId: string,
  limit = 100,
): Promise<StoredProspectsResponse> {
  try {
    const response = await apiClient.get<StoredProspectsResponse>(`/api/prospects/${userId}`, {
      params: { limit },
    });
    return response.data;
  } catch (error) {
    throw new Error(getErrorMessage(error, "Failed to retrieve prospects"));
  }
}

/** Deletes one stored prospect by user ID and place ID. */
export async function deleteProspect(userId: string, placeId: string): Promise<void> {
  try {
    await apiClient.delete(`/api/prospects/${userId}/${placeId}`);
  } catch (error) {
    throw new Error(getErrorMessage(error, "Failed to delete prospect"));
  }
}

/** Creates a Stripe Checkout session for a paid plan. */
export async function createCheckoutSession(
  userId: string,
  priceId: string,
): Promise<CheckoutSessionResponse> {
  try {
    const response = await apiClient.post<CheckoutSessionResponse>("/api/create-checkout-session", {
      user_id: userId,
      price_id: priceId,
    });
    return response.data;
  } catch (error) {
    throw new Error(getErrorMessage(error, "Failed to create checkout session"));
  }
}

/** Creates a Stripe Billing Portal session for the current user. */
export async function createBillingPortal(userId: string): Promise<BillingPortalResponse> {
  try {
    const response = await apiClient.post<BillingPortalResponse>("/api/billing-portal", {
      user_id: userId,
    });
    return response.data;
  } catch (error) {
    throw new Error(getErrorMessage(error, "Failed to open billing portal"));
  }
}

/** Submits product feedback for weekly review. */
export async function submitFeedback(
  userId: string,
  feedback: string,
  sourcePath: string,
): Promise<FeedbackResponse> {
  try {
    const response = await apiClient.post<FeedbackResponse>("/api/feedback", {
      user_id: userId,
      feedback,
      source_path: sourcePath,
    });
    return response.data;
  } catch (error) {
    throw new Error(getErrorMessage(error, "Failed to submit feedback"));
  }
}

/** Fetches admin dashboard metrics using a manually entered admin key. */
export async function getAdminStats(adminKey: string): Promise<AdminStats> {
  try {
    const response = await apiClient.get<AdminStats>("/api/admin/stats", {
      params: { admin_key: adminKey },
    });
    return response.data;
  } catch (error) {
    throw new Error(getErrorMessage(error, "Failed to load admin stats"));
  }
}
