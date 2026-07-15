/** Admin dashboard for post-launch usage metrics.
 *  Uses a manually entered admin key and the backend stats endpoint.
 */

import Head from "next/head";
import { FormEvent, useState } from "react";

import { AdminStatCard, Alert } from "../../components/ui";
import { getAdminStats } from "../../lib/api";
import styles from "../../styles/prospecting.module.css";
import type { AdminStats } from "../../types/prospect";

/** Renders high-level SaaS metrics for manual weekly review. */
export default function AdminDashboardPage(): JSX.Element {
  const [adminKey, setAdminKey] = useState("");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  /** Fetches admin metrics after the key is submitted. */
  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      setStats(await getAdminStats(adminKey));
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not load metrics");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Head>
        <title>Admin Dashboard</title>
      </Head>
      <main className={styles.main}>
        <section className={styles.pageIntro}>
          <p className={styles.kicker}>Admin</p>
          <h1>Growth metrics</h1>
          <p>Use these numbers during the weekly review to decide what to improve next.</p>
        </section>
        <form className={styles.adminKeyForm} onSubmit={handleSubmit}>
          <label className={styles.inputGroup} htmlFor="admin-key">
            <span>Admin key</span>
            <input
              id="admin-key"
              type="password"
              value={adminKey}
              onChange={(event) => setAdminKey(event.target.value)}
              required
            />
          </label>
          <button className={styles.searchButton} type="submit" disabled={loading}>
            {loading ? "Loading" : "Load metrics"}
          </button>
        </form>
        {error ? <Alert title="Admin error" message={error} /> : null}
        {stats ? (
          <section className={styles.statsGrid} aria-label="Admin metrics">
            <AdminStatCard label="Total users" value={stats.total_users} />
            <AdminStatCard label="Free users" value={stats.free_users} />
            <AdminStatCard label="Paid users" value={stats.paid_users} />
            <AdminStatCard label="Total searches" value={stats.total_searches} />
          </section>
        ) : null}
      </main>
    </>
  );
}

