const BASE = "http://localhost:8000";

// Every endpoint needs X-User-Id, and every failure comes back as
// { "error": { "code": ..., "message": ... } }. Unwrapping it here means each
// caller only has to catch one thing.
export async function api(user, path, options = {}) {
  const response = await fetch(BASE + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": user,
    },
  });

  // DELETE answers with an empty body, so JSON.parse would throw on "".
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw body.error;
  }
  return body;
}
