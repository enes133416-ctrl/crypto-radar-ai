import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import ScannerTable from "../src/components/ScannerTable";
import Dashboard from "../src/pages/Dashboard";
import { coin } from "./fixtures";

describe("terminal componentleri", () => {
  it("coin listesini yükler ve skor açıklamasını açar", async () => {
    render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><ScannerTable rows={[coin]} /></MemoryRouter>);
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.getByText("88.0")).toBeInTheDocument();
    expect(screen.getAllByText("%70.0").length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "BTCUSDT detayını aç" }));
    expect(screen.getByText(/Hacim ortalamanın 3 katı/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Detay/ })).toHaveAttribute("href", "/coin/spot/BTCUSDT");
  });

  it("API hatasında sahte coin yerine açık hata ekranı gösterir", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    render(<Dashboard />);
    await waitFor(() => expect(screen.getByText("Veri alınamadı")).toBeInTheDocument());
    expect(screen.getByText(/Backend'e ulaşılamıyor/)).toBeInTheDocument();
    expect(screen.queryByText("BTCUSDT")).not.toBeInTheDocument();
  });
});
