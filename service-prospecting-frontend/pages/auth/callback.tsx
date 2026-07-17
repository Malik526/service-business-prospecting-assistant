/** OAuth callback handler page.
 *  Receives users after Google OAuth, waits for the Supabase browser session,
 *  then redirects authenticated users to the prospecting workspace.
 */

import Head from "next/head";
import { useRouter } from "next/router";
import { useEffect } from "react";

import { appContent } from "../../lib/content";
import { supabase } from "../../lib/supabase";
import styles from "../../styles/prospecting.module.css";

const SESSION_CHECK_ATTEMPTS = 8;
const SESSION_CHECK_DELAY_MS = 250;

/** Pauses briefly between session checks while Supabase stores OAuth state. */
function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

/** Waits for Supabase to expose the session created by the OAuth callback. */
async function waitForSession() {
  for (let attempt = 0; attempt < SESSION_CHECK_ATTEMPTS; attempt += 1) {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (session) {
      return session;
    }

    await wait(SESSION_CHECK_DELAY_MS);
  }

  return null;
}

/** Handles Supabase OAuth completion and redirects based on session status. */
export default function CallbackPage(): JSX.Element {
  const router = useRouter();

  useEffect(() => {
    let mounted = true;

    /** Checks the OAuth-created session before sending users into the app. */
    async function handleAuthCallback(): Promise<void> {
      try {
        const session = await waitForSession();
        if (!mounted) {
          return;
        }

        if (session) {
          await router.push("/prospecting");
          return;
        }

        await router.push("/auth");
      } catch (error) {
        await router.push("/auth");
      }
    }

    handleAuthCallback();

    return () => {
      mounted = false;
    };
  }, [router]);

  return (
    <>
      <Head>
        <title>{`Completing sign-in | ${appContent.title}`}</title>
      </Head>
      <main className={styles.authShell}>
        <section className={styles.authPanel} role="status" aria-live="polite">
          <p className={styles.kicker}>Account</p>
          <h1>Completing sign-in</h1>
          <p>Please wait while we finish setting up your session.</p>
        </section>
      </main>
    </>
  );
}
