/** Feedback form for post-launch product learning.
 *  Props: onSubmit sends text to the backend; loading controls disabled state.
 */

import { FormEvent, useState } from "react";

import styles from "../../styles/prospecting.module.css";

interface FeedbackFormProps {
  loading: boolean;
  onSubmit: (feedback: string) => Promise<void>;
}

/** Renders a textarea form for product feedback submissions. */
export function FeedbackForm({ loading, onSubmit }: FeedbackFormProps): JSX.Element {
  const [feedback, setFeedback] = useState("");

  /** Sends the current feedback text and clears the form after success. */
  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await onSubmit(feedback);
    setFeedback("");
  }

  return (
    <form className={styles.feedbackForm} onSubmit={handleSubmit}>
      <label className={styles.inputGroup} htmlFor="feedback">
        <span>Feedback</span>
        <textarea
          id="feedback"
          value={feedback}
          onChange={(event) => setFeedback(event.target.value)}
          placeholder="What should improve before this is worth paying for?"
          required
        />
      </label>
      <button className={styles.searchButton} type="submit" disabled={loading}>
        {loading ? "Submitting" : "Submit feedback"}
      </button>
    </form>
  );
}

