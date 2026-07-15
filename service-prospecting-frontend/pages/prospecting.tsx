/** Main prospecting page.
 *  Coordinates search form state, backend API calls, results display, and CSV export.
 */

import Head from "next/head";
import { useRef, useState } from "react";

import { SearchForm } from "../components/forms";
import { ResultsTable } from "../components/results";
import { Alert, EmptyState, LoadingSpinner } from "../components/ui";
import { appContent } from "../lib/content";
import { buildProspectCsv, downloadCsv } from "../lib/csv";
import { searchProspects } from "../lib/api";
import { getOrCreateUserId } from "../lib/user";
import styles from "../styles/prospecting.module.css";
import type { Prospect } from "../types/prospect";

/** Renders the full prospect search and results workflow. */
export default function ProspectingPage(): JSX.Element {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [count, setCount] = useState(0);
  const [duplicateCount, setDuplicateCount] = useState(0);
  const [hasSearched, setHasSearched] = useState(false);
  const lastSearchRef = useRef("initial");

  /** Calls the backend search endpoint and updates result state. */
  async function handleSearch(zipCode: string, radius: number, categories: string): Promise<void> {
    setLoading(true);
    setError("");
    setProspects([]);
    setHasSearched(true);

    try {
      const response = await searchProspects({
        zip_code: zipCode,
        radius,
        categories: categories || undefined,
        user_id: getOrCreateUserId(),
      });

      setProspects(response.prospects || []);
      setCount(response.count || 0);
      setDuplicateCount(response.duplicate_count || 0);
      lastSearchRef.current = `${zipCode}-${radius}-${categories || "all"}`;
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Search failed");
      setCount(0);
      setDuplicateCount(0);
    } finally {
      setLoading(false);
    }
  }

  /** Exports the current result set to a timestamped CSV file. */
  function handleExport(): void {
    const csv = buildProspectCsv(prospects);
    const timestamp = new Date().toISOString().slice(0, 10);
    downloadCsv(csv, `prospects-${lastSearchRef.current}-${timestamp}.csv`);
  }

  return (
    <>
      <Head>
        <title>{appContent.title}</title>
        <meta name="description" content={appContent.description} />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className={styles.pageShell}>
        <header className={styles.header}>
          <div className={styles.headerInner}>
            <p className={styles.kicker}>{appContent.eyebrow}</p>
            <h1>{appContent.title}</h1>
            <p>{appContent.tagline}</p>
          </div>
        </header>

        <main className={styles.main}>
          <SearchForm onSearch={handleSearch} loading={loading} />

          {error ? <Alert title={appContent.errorTitle} message={error} /> : null}
          {loading ? <LoadingSpinner /> : null}
          {!loading && prospects.length > 0 ? (
            <ResultsTable
              prospects={prospects}
              count={count}
              duplicateCount={duplicateCount}
              onExport={handleExport}
            />
          ) : null}
          {!loading && !error && prospects.length === 0 && hasSearched ? (
            <EmptyState title={appContent.noResultsTitle} body={appContent.noResultsBody} />
          ) : null}
          {!loading && !error && prospects.length === 0 && !hasSearched ? (
            <EmptyState title={appContent.emptyTitle} body={appContent.emptyBody} />
          ) : null}
        </main>

        <footer className={styles.footer}>{appContent.footer}</footer>
      </div>
    </>
  );
}

