// Thin fetch wrapper: adds the bearer token, surfaces FastAPI `detail` messages,
// and signals a 401 so the app can send the user back to the login screen.

const TOKEN_KEY = "platform_token";
const USER_KEY = "platform_user";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  user: () => sessionStorage.getItem(USER_KEY),
  set(token: string, user: string) {
    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(USER_KEY, user);
  },
  clear() {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
  },
};

let onUnauthorized: () => void = () => {};
export const setUnauthorizedHandler = (handler: () => void) => {
  onUnauthorized = handler;
};

async function readError(resp: Response): Promise<string> {
  const text = await resp.text();
  try {
    const body = JSON.parse(text);
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((d: { msg: string }) => d.msg).join(" ; ");
  } catch {
    /* not JSON */
  }
  return text || resp.statusText;
}

async function request(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const resp = await fetch(path, { ...options, headers });
  if (resp.status === 401 && !path.startsWith("/auth/login")) onUnauthorized();
  if (!resp.ok) throw new ApiError(resp.status, await readError(resp));
  return resp;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  return (await request(path, options)).json() as Promise<T>;
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const put = <T>(path: string, body: unknown) => api<T>(path, { method: "PUT", body: JSON.stringify(body) });

/** Downloads an authenticated response as a file (a plain <a href> can't send the bearer token). */
export async function download(path: string, filename: string): Promise<void> {
  const blob = await (await request(path)).blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
