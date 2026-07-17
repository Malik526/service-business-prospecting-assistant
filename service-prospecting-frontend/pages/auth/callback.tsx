/** OAuth callback handler page.
 *  Manually consumes Supabase tokens from the URL fragment, verifies the
 *  resulting browser session, and routes users to the appropriate page.
 */

import Head from "next/head";
import { useRouter } from "next/router";
import { useEffect } from "react";

import { appContent } from "../../lib/content";
import { supabase } from "../../lib/supabase";
import styles from "../../styles/prospecting.module.css";

/** Extracts OAuth tokens from the URL fragment without exposing their values. */
function getOAuthTokens(): { accessToken: string | null; refreshToken: string | null } {
  const params = new URLSearchParams(window.location.hash.substring(1));

  return {
    accessToken: params.get("access_token"),
    refreshToken: params.get("refresh_token"),
  };
}

/** Handles Supabase OAuth completion and redirects based on verified session state. */
export default function CallbackPage(): JSX.Element {
  const router = useRouter();

  useEffect(() => {
    let mounted = true;

    /** Sets tokens from the callback URL, then confirms the persisted session. */
    async function handleAuthCallback(): Promise<void> {
      try {
        const { accessToken, refreshToken } = getOAuthTokens();

        console.log(`Access token from URL: ${accessToken ? "Found" : "Not found"}`);

        if (accessToken && refreshToken) {
          const { error } = await supabase.auth.setSession({
            access_token: accessToken,
            refresh_token: refreshToken,
          });

          if (error) {
            console.error("Failed to set session:", error.message);
            if (mounted) {
              await router.replace("/auth");
            }
            return;
          }

          window.history.replaceState(null, "", window.location.pathname);
          console.log("Session set successfully.");
        }

        const {
          data: { session },
          error: sessionError,
        } = await supabase.auth.getSession();

        if (sessionError) {
          throw sessionError;
        }

        if (!mounted) {
          return;
        }

        if (session) {
          console.log("Session confirmed, redirecting to prospecting.");
          await router.replace("/prospecting");
          return;
        }

        console.log("No session found after parsing, redirecting to auth.");
        await router.replace("/auth");
      } catch (error) {
        console.error("Auth callback error:", error);
        if (mounted) {
          await router.replace("/auth");
        }
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
          <p>Please wait while we secure your session.</p>
        </section>
      </main>
    </>
  );
}
