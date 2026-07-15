/** Manages the lightweight browser user ID used before full authentication exists.
 *  The stored ID lets repeated searches dedupe against the same DynamoDB partition.
 */

const USER_ID_KEY = "service-prospecting-user-id";

/** Returns a stable local user ID, creating one when needed. */
export function getOrCreateUserId(): string {
  if (typeof window === "undefined") {
    return "guest-server";
  }

  const existingUserId = window.localStorage.getItem(USER_ID_KEY);
  if (existingUserId) {
    return existingUserId;
  }

  const nextUserId = `guest-${crypto.randomUUID()}`;
  window.localStorage.setItem(USER_ID_KEY, nextUserId);
  return nextUserId;
}

