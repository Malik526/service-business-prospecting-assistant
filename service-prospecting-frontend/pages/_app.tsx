/** Next.js app wrapper.
 *  Imports global CSS once and renders the active page component.
 */

import type { AppProps } from "next/app";

import "../styles/globals.css";

/** Renders the current Next.js page. */
export default function App({ Component, pageProps }: AppProps): JSX.Element {
  return <Component {...pageProps} />;
}

