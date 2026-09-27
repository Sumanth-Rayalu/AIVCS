const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(
  /\/$/,
  "",
);

async function request(path, { method = "GET", token, body } = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw new Error(
      "Could not reach the AIVCS backend. Check that it is running.",
    );
  }

  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      result.detail ?? `Request failed (${response.status}).`,
    );
    error.status = response.status;
    throw error;
  }
  return result;
}

export const api = {
  login: (credentials) =>
    request("/api/auth/login", { method: "POST", body: credentials }),
  register: (details) =>
    request("/api/auth/register", { method: "POST", body: details }),
  currentUser: (token) => request("/api/auth/me", { token }),
  logout: (token) => request("/api/auth/logout", { method: "POST", token }),
  updateUserData: (token, userData) =>
    request("/api/userdata", { method: "PUT", token, body: { userData } }),
};
