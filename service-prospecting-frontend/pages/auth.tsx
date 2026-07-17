/** Authentication page for Supabase sign-in.
 *  Renders Supabase Auth UI and redirects signed-in users to the prospecting workspace.
 */

import { Auth } from "@supabase/auth-ui-react";
import { ThemeSupa } from "@supabase/auth-ui-shared";
import Head from "next/head";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";

import { EmptyState, LoadingSpinner } from "../components/ui";
import { appContent } from "../lib/content";
import { isSupabaseConfigured, supabase } from "../lib/supabase";
import styles from "../styles/prospecting.module.css";

/** Renders Supabase login and setup guidance. */
export default function AuthPage(): JSX.Element {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [callbackUrl, setCallbackUrl] = useState("");

  useEffect(() => {
    let mounted = true;

    /** Redirects an already signed-in user to the main app. */
    async function checkSession(): Promise<void> {
      if (mounted) {
        setCallbackUrl(`${window.location.origin}/auth/callback`);
      }

      if (!isSupabaseConfigured) {
        if (mounted) {
          setLoading(false);
        }
        return;
      }

      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (session) {
        await router.push("/prospecting");
        return;
      }
      if (mounted) {
        setLoading(false);
      }
    }

    checkSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (event === "SIGNED_IN" && session) {
        await router.push("/prospecting");
      }
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [router]);

  return (
    <>
      <Head>
        <title>{appContent.authTitle}</title>
      </Head>
      <main className={styles.authShell}>
        {loading ? <LoadingSpinner /> : null}
        {!loading && !isSupabaseConfigured ? (
          <EmptyState title={appContent.setupTitle} body={appContent.setupBody} />
        ) : null}
        {!loading && isSupabaseConfigured ? (
          <section className={styles.authPanel}>
            <p className={styles.kicker}>Account</p>
            <h1>{appContent.authTitle}</h1>
            <p>{appContent.authBody}</p>
            <Auth
              supabaseClient={supabase}
              appearance={{ theme: ThemeSupa }}
              providers={["google"]}
              redirectTo={callbackUrl}
              onlyThirdPartyProviders={false}
            />
          </section>
        ) : null}
      </main>
    </>
  );
}
