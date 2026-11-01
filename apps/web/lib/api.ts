export async function api<T>(
  path: string,
  org?: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-OrderMesh": "1",
      ...(org ? { "X-Organization-ID": org } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "The server could not complete this request." }));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : data.detail?.map((e: { msg: string }) => e.msg).join("; ") ||
            "Request failed",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export async function allPages<T>(path: string, org: string): Promise<T[]> {
  const results: T[] = [];
  for (let offset = 0; ; offset += 500) {
    const page = await api<T[]>(`${path}?limit=500&offset=${offset}`, org);
    results.push(...page);
    if (page.length < 500) return results;
  }
}
export const money = (minor: number) =>
  new Intl.NumberFormat("en-LK", {
    style: "currency",
    currency: "LKR",
    maximumFractionDigits: 2,
  }).format(minor / 100);
export const date = (value: string) =>
  new Date(
    value.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`,
  ).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Colombo",
  });
