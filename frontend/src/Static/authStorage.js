const SESSION_KEY = "aivcs.session.v1";

export function getSessionToken() {
  const storedValue = localStorage.getItem(SESSION_KEY);
  if (!storedValue) return null;

  if (storedValue.startsWith("{")) {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }
  return storedValue;
}

export function storeSession(token) {
  localStorage.setItem(SESSION_KEY, token);
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}
