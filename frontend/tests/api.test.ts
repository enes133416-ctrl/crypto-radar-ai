import { describe, it, expect, vi } from "vitest";
import { fetchHealth } from "../src/services/api";

describe("fetchHealth", () => {
  it("başarılı yanıtı döndürür", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) }));
    expect((await fetchHealth("http://x")).status).toBe("ok");
  });
  it("HTTP hatasında hata fırlatır", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    await expect(fetchHealth("http://x")).rejects.toThrow("HTTP 500");
  });
});
