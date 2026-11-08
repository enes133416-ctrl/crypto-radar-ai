import { useEffect, useRef } from "react";
import { ColorType, createChart, CrosshairMode, type IChartApi, type UTCTimestamp } from "lightweight-charts";
import type { Candle } from "../types/api";

export default function PriceChart({ candles, height = 380 }: { candles: Candle[]; height?: number }) {
  const container = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  useEffect(() => {
    if (!container.current || candles.length === 0) return;
    const chart = createChart(container.current, {
      height,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#94a3b8", fontSize: 11 },
      grid: { vertLines: { color: "#1e293b66" }, horzLines: { color: "#1e293b66" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#334155" }, timeScale: { borderColor: "#334155", timeVisible: true, secondsVisible: false },
      localization: { locale: "tr-TR" },
    });
    chartRef.current = chart;
    const series = chart.addCandlestickSeries({ upColor: "#34d399", downColor: "#fb7185", wickUpColor: "#34d399", wickDownColor: "#fb7185", borderVisible: false });
    series.setData(candles.map((c) => ({ time: (c.open_time / 1000) as UTCTimestamp, open: c.open, high: c.high, low: c.low, close: c.close })));
    const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "volume", lastValueVisible: false, priceLineVisible: false });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    volume.setData(candles.map((c) => ({ time: (c.open_time / 1000) as UTCTimestamp, value: c.quote_volume, color: c.close >= c.open ? "#10b98155" : "#f43f5e55" })));
    chart.timeScale().fitContent();
    const observer = new ResizeObserver((entries) => { const width = entries[0]?.contentRect.width; if (width) chart.applyOptions({ width }); });
    observer.observe(container.current);
    return () => { observer.disconnect(); chart.remove(); chartRef.current = null; };
  }, [candles, height]);
  return <div ref={container} className="w-full" data-testid="price-chart" />;
}
