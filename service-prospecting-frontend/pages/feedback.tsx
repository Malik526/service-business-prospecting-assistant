/** Feedback page for post-launch learning.
 *  Collects user feedback and sends it to the backend feedback endpoint.
 */

import Head from "next/head";
import { useState } from "react";

import { FeedbackForm } from "../components/forms";
import { Alert, EmptyState, LoadingSpinner } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { submitFeedback } from "../lib/api";
import { appContent } from "../lib/content";
import styles from "../styles/prospecting.module.css";

/** Renders the product feedback workflow. */
export default function FeedbackPage(): JSX.Element {
  const { authLoading, user, configured } = useAuth();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  /** Sends feedback to the backend and confirms submission. */
  async function handleSubmit(feedback: string): Promise<void> {
    setLoading(true);
    setError("");
    setMessage("");
    try {
      await submitFeedback(user?.id || "", feedback, "/feedback");
      setMessage("Thanks. Your feedback was recorded for the weekly review.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not submit feedback");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Head>
        <title>{appContent.feedbackTitle}</title>
      </Head>
      <main className={styles.main}>
        {authLoading ? <LoadingSpinner /> : null}
        {!authLoading && !configured ? (
          <EmptyState title={appContent.setupTitle} body={appContent.setupBody} />
        ) : null}
        {!authLoading && configured && user ? (
          <section className={styles.authPanel}>
            <p className={styles.kicker}>Feedback</p>
            <h1>{appContent.feedbackTitle}</h1>
            <p>{appContent.feedbackBody}</p>
            {message ? <p className={styles.successText}>{message}</p> : null}
            {error ? <Alert title="Feedback error" message={error} /> : null}
            <FeedbackForm loading={loading} onSubmit={handleSubmit} />
          </section>
        ) : null}
      </main>
    </>
  );
}

