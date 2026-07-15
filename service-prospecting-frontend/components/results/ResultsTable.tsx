/** Results table for prospect search output.
 *  Props: prospects are displayed rows; count is the backend count; onExport downloads CSV.
 */

import { Download, ExternalLink, Globe, MapPin, Phone } from "lucide-react";

import styles from "../../styles/prospecting.module.css";
import type { Prospect } from "../../types/prospect";

interface ResultsTableProps {
  prospects: Prospect[];
  count: number;
  duplicateCount: number;
  onExport: () => void;
}

/** Returns the CSS class used to visually group lead scores. */
function scoreClassName(score: number): string {
  if (score >= 8) {
    return styles.scoreHigh;
  }
  if (score >= 6) {
    return styles.scoreMedium;
  }
  return styles.scoreLow;
}

/** Renders a responsive table of prospect rows and export controls. */
export function ResultsTable({
  prospects,
  count,
  duplicateCount,
  onExport,
}: ResultsTableProps): JSX.Element | null {
  if (prospects.length === 0) {
    return null;
  }

  return (
    <section className={styles.resultsPanel} aria-labelledby="results-heading">
      <div className={styles.resultsHeader}>
        <div>
          <p className={styles.kicker}>{duplicateCount} duplicates skipped</p>
          <h2 id="results-heading">{count} prospects found</h2>
        </div>
        <button className={styles.exportButton} type="button" onClick={onExport}>
          <Download aria-hidden="true" size={18} />
          <span>Export CSV</span>
        </button>
      </div>

      <div className={styles.tableScroller}>
        <table className={styles.resultsTable}>
          <thead>
            <tr>
              <th scope="col">Business</th>
              <th scope="col">Category</th>
              <th scope="col">Rating</th>
              <th scope="col">Reviews</th>
              <th scope="col">Score</th>
              <th scope="col">Distance</th>
              <th scope="col">Contact</th>
              <th scope="col">Links</th>
            </tr>
          </thead>
          <tbody>
            {prospects.map((prospect) => (
              <tr key={prospect.place_id}>
                <td>
                  <a
                    className={styles.businessLink}
                    href={prospect.google_maps_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <span>{prospect.business_name}</span>
                    <ExternalLink aria-hidden="true" size={14} />
                  </a>
                  <span className={styles.address}>{prospect.address}</span>
                </td>
                <td>{prospect.category}</td>
                <td>{prospect.rating > 0 ? prospect.rating.toFixed(1) : "N/A"}</td>
                <td>{prospect.review_count}</td>
                <td>
                  <span className={`${styles.scorePill} ${scoreClassName(prospect.lead_score)}`}>
                    {prospect.lead_score.toFixed(1)}
                  </span>
                </td>
                <td>{prospect.distance_miles.toFixed(1)} mi</td>
                <td>
                  {prospect.phone ? (
                    <a className={styles.iconLink} href={`tel:${prospect.phone}`}>
                      <Phone aria-hidden="true" size={15} />
                      <span>{prospect.phone}</span>
                    </a>
                  ) : (
                    <span className={styles.mutedText}>N/A</span>
                  )}
                </td>
                <td>
                  <div className={styles.linkCluster}>
                    {prospect.website ? (
                      <a
                        className={styles.squareLink}
                        href={prospect.website}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`Visit ${prospect.business_name} website`}
                      >
                        <Globe aria-hidden="true" size={16} />
                      </a>
                    ) : null}
                    <a
                      className={styles.squareLink}
                      href={prospect.google_maps_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={`Open ${prospect.business_name} on Google Maps`}
                    >
                      <MapPin aria-hidden="true" size={16} />
                    </a>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

