const API = "https://cyberrakshak-api.onrender.com";
const ADMIN_USER = "admin";
const ADMIN_PASS = "Sentinel@123";
const MAX_PARAMS = 12;

async function fetchIds(path: string): Promise<{ id: string }[]> {
  const login = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: ADMIN_USER, password: ADMIN_PASS }),
  });
  if (!login.ok) throw new Error(`login failed (${login.status})`);
  const { access_token } = (await login.json()) as { access_token: string };

  const res = await fetch(`${API}/api/${path}?limit=${MAX_PARAMS}`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });
  if (!res.ok) throw new Error(`list failed (${res.status})`);
  const body = (await res.json()) as unknown;
  const items = (Array.isArray(body) ? body : (body as { items?: { id: string }[] }).items) ?? [];
  return (items as { id: string }[])
    .map((i) => ({ id: String(i.id) }))
    .filter((i) => i.id.length > 0)
    .slice(0, MAX_PARAMS);
}

export async function generateStaticParamsFor(path: string): Promise<{ id: string }[]> {
  try {
    const params = await fetchIds(path);
    if (params.length > 0) return params;
    throw new Error("no ids returned");
  } catch (err) {
    console.warn(`[static-params] falling back to demo param for /${path}:`, err);
    return [{ id: "demo" }];
  }
}
