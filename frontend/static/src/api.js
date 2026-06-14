async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "include",
    ...options,
    headers: options.body ? { "Content-Type": "application/json", ...options.headers } : options.headers,
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof body === "object" ? body.detail || JSON.stringify(body) : body;
    throw new Error(message || `HTTP ${response.status}`);
  }
  return body;
}

export function getJson(path) {
  return request(path);
}

export function postJson(path, payload = {}) {
  return request(path, { method: "POST", body: JSON.stringify(payload) });
}

