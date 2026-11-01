import { test, expect } from "@playwright/test";
import { NextRequest } from "next/server";
import { proxy } from "../proxy";

test("local browser pages use the fixed configured HTTPS origin without weakening POST protection", () => {
  const previous = process.env.ORDERMESH_APP_ORIGIN;
  try {
    process.env.ORDERMESH_APP_ORIGIN = "https://dashboard.example.com";
    const local = new NextRequest(
      "http://localhost:3000/dashboard/inbox?tab=all",
      { headers: { host: "localhost:3000" } },
    );
    const response = proxy(local);
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://dashboard.example.com/dashboard/inbox?tab=all",
    );
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(
      proxy(
        new NextRequest("http://localhost:3000/sign-in", {
          headers: { host: "dashboard.example.com" },
        }),
      ).headers.get("location"),
    ).toBeNull();
    expect(
      proxy(
        new NextRequest("http://localhost:3000/sign-in", {
          method: "POST",
          headers: { host: "localhost:3000" },
        }),
      ).headers.get("location"),
    ).toBeNull();
    process.env.ORDERMESH_APP_ORIGIN = "http://localhost:3000";
    expect(proxy(local).headers.get("location")).toBeNull();
  } finally {
    if (previous === undefined) delete process.env.ORDERMESH_APP_ORIGIN;
    else process.env.ORDERMESH_APP_ORIGIN = previous;
  }
});
