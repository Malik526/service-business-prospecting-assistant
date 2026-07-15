/** Home route for the frontend app.
 *  Reuses the prospecting workspace as the first screen instead of a marketing page.
 */

import ProspectingPage from "./prospecting";

/** Renders the main prospecting workspace at the root URL. */
export default function HomePage(): JSX.Element {
  return <ProspectingPage />;
}

