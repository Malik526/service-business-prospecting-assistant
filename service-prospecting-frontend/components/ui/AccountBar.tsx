/** Account control strip for authenticated pages.
 *  Props: email, onSignOut handler, and optional billing/feedback links.
 */

import Link from "next/link";
import { LogOut } from "lucide-react";

import styles from "../../styles/prospecting.module.css";

interface AccountBarProps {
  email: string;
  onSignOut: () => void;
}

/** Renders account navigation and sign-out controls. */
export function AccountBar({ email, onSignOut }: AccountBarProps): JSX.Element {
  return (
    <nav className={styles.accountBar} aria-label="Account navigation">
      <span>{email}</span>
      <Link href="/upgrade">Plans</Link>
      <Link href="/feedback">Feedback</Link>
      <button type="button" onClick={onSignOut}>
        <LogOut aria-hidden="true" size={16} />
        <span>Sign out</span>
      </button>
    </nav>
  );
}

