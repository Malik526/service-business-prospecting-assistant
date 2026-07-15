/** Builds and downloads CSV exports from prospect result rows.
 *  PapaParse handles escaping so quoted business names and addresses remain valid.
 */

import Papa from "papaparse";

import type { Prospect } from "../types/prospect";

const csvHeaders = [
  "Business Name",
  "Category",
  "Rating",
  "Reviews",
  "Lead Score",
  "Weighted Reputation Score",
  "Distance (mi)",
  "Address",
  "Phone",
  "Website",
  "Google Maps",
  "Email",
  "Instagram URL",
];

/** Converts prospect data into CSV text. */
export function buildProspectCsv(prospects: Prospect[]): string {
  const rows = prospects.map((prospect) => ({
    "Business Name": prospect.business_name,
    Category: prospect.category,
    Rating: prospect.rating,
    Reviews: prospect.review_count,
    "Lead Score": prospect.lead_score,
    "Weighted Reputation Score": prospect.weighted_reputation_score,
    "Distance (mi)": prospect.distance_miles,
    Address: prospect.address,
    Phone: prospect.phone || "",
    Website: prospect.website || "",
    "Google Maps": prospect.google_maps_url,
    Email: prospect.email || "",
    "Instagram URL": prospect.instagram_url || "",
  }));

  return Papa.unparse(rows, { columns: csvHeaders });
}

/** Downloads a CSV file in the browser. */
export function downloadCsv(csv: string, filename: string): void {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

