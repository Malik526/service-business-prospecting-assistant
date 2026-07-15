/** Provides typed HTTP helpers for the prospecting backend API.
 *  All API calls route through this file so base URL and error handling stay consistent.
 */

import axios, { AxiosError } from "axios";

import type {
  ApiErrorPayload,
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
