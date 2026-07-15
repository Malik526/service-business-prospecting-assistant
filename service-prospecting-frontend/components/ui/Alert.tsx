/** Alert component for API and validation messages.
 *  Props: title and message render a compact, accessible status panel.
 */

import { AlertCircle } from "lucide-react";

import styles from "../../styles/prospecting.module.css";

interface AlertProps {
  title: string;
  message: string;
}

/** Renders an error alert with clear status semantics. */
export function Alert({ title, message }: AlertProps): JSX.Element {
  return (
    <div className={styles.alert} role="alert">
      <AlertCircle aria-hidden="true" size={18} />
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}

