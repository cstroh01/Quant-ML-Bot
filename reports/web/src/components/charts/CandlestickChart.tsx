import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineSeries,
} from 'lightweight-charts';
import type { BarData, TradeRecord } from '../../types/api';

interface CandlestickChartProps {
  data: BarData[];
  trades?: TradeRecord[];
  colorblindMode: boolean;
  height?: number;
  shortWindow?: number;
  longWindow?: number;
}

export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  data,
  trades = [],
  colorblindMode,
  height = 450,
  shortWindow = 10,
  longWindow = 30,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<ReturnType<typeof createChart> | null>(null);

  const [showShortSma, setShowShortSma] = useState(true);
  const [showLongSma, setShowLongSma] = useState(true);
  const [showMarkers, setShowMarkers] = useState(true);
  const [selectedTimeframe, setSelectedTimeframe] = useState<'1Y' | '2Y' | '5Y' | 'All'>('All');

  // Compute SMAs
  const shortSmaData = useMemo(() => {
    if (data.length < shortWindow) return [];
    const points = [];
    for (let i = 0; i < data.length; i++) {
      if (i < shortWindow - 1) continue;
      let sum = 0;
      for (let j = 0; j < shortWindow; j++) {
        sum += data[i - j].close;
      }
      points.push({ time: data[i].time, value: parseFloat((sum / shortWindow).toFixed(2)) });
    }
    return points;
  }, [data, shortWindow]);

  const longSmaData = useMemo(() => {
    if (data.length < longWindow) return [];
    const points = [];
    for (let i = 0; i < data.length; i++) {
      if (i < longWindow - 1) continue;
      let sum = 0;
      for (let j = 0; j < longWindow; j++) {
        sum += data[i - j].close;
      }
      points.push({ time: data[i].time, value: parseFloat((sum / longWindow).toFixed(2)) });
    }
    return points;
  }, [data, longWindow]);

  useEffect(() => {
    if (!chartContainerRef.current || data.length === 0) return;

    const upColor = colorblindMode ? '#0284C7' : '#10B981';
    const downColor = colorblindMode ? '#D97706' : '#F43F5E';

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#090C10' },
        textColor: '#8E9BAE',
      },
      grid: {
        vertLines: { color: '#141A24' },
        horzLines: { color: '#141A24' },
      },
      crosshair: {
        vertLine: { color: '#38BDF8', width: 1, style: 2 },
        horzLine: { color: '#38BDF8', width: 1, style: 2 },
      },
      timeScale: {
        borderColor: '#1C2331',
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: '#1C2331',
      },
      width: chartContainerRef.current.clientWidth,
      height,
    });
    chartInstanceRef.current = chart;

    // Candlestick series
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor,
      downColor,
      borderVisible: false,
      wickUpColor: upColor,
      wickDownColor: downColor,
    });

    const candleData = data.map((d) => ({
      time: d.time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    candlestickSeries.setData(candleData);

    // Volume overlay
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.82,
        bottom: 0,
      },
    });

    const volumeData = data.map((d) => ({
      time: d.time,
      value: d.volume,
      color: d.close >= d.open ? `${upColor}40` : `${downColor}40`,
    }));
    volumeSeries.setData(volumeData);

    // Short SMA overlay
    if (showShortSma && shortSmaData.length > 0) {
      const shortLine = chart.addSeries(LineSeries, {
        color: '#06B6D4', // Cyan
        lineWidth: 2,
        title: `SMA ${shortWindow}`,
      });
      shortLine.setData(shortSmaData);
    }

    // Long SMA overlay
    if (showLongSma && longSmaData.length > 0) {
      const longLine = chart.addSeries(LineSeries, {
        color: '#F59E0B', // Amber
        lineWidth: 2,
        title: `SMA ${longWindow}`,
      });
      longLine.setData(longSmaData);
    }

    // Trade Markers Overlay
    if (showMarkers && trades.length > 0) {
      const markers: any[] = [];
      const buyColor = colorblindMode ? '#0284C7' : '#10B981';
      const sellColor = colorblindMode ? '#D97706' : '#F43F5E';

      // Sort trades by date to ensure proper ordering
      const sortedTrades = [...trades].sort((a, b) => a.entry_date.localeCompare(b.entry_date));

      for (const t of sortedTrades) {
        markers.push({
          time: t.entry_date,
          position: 'belowBar',
          color: buyColor,
          shape: 'arrowUp',
          text: `BUY @ $${t.entry_price.toFixed(1)}`,
        });
        markers.push({
          time: t.exit_date,
          position: 'aboveBar',
          color: sellColor,
          shape: 'arrowDown',
          text: `SELL @ $${t.exit_price.toFixed(1)} (${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(0)})`,
        });
      }

      // Sort all markers strictly ascending by time
      markers.sort((a, b) => a.time.localeCompare(b.time));
      try {
        createSeriesMarkers(candlestickSeries, markers);
      } catch (err) {
        console.warn('Could not attach series markers:', err);
      }
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartInstanceRef.current = null;
    };
  }, [
    data,
    trades,
    colorblindMode,
    height,
    showShortSma,
    showLongSma,
    showMarkers,
    shortSmaData,
    longSmaData,
    shortWindow,
    longWindow,
  ]);

  // Handle Timeframe zoom
  const handleTimeframeChange = (tf: '1Y' | '2Y' | '5Y' | 'All') => {
    setSelectedTimeframe(tf);
    const chart = chartInstanceRef.current;
    if (!chart || data.length === 0) return;

    if (tf === 'All') {
      chart.timeScale().fitContent();
      return;
    }

    const lastDate = new Date(data[data.length - 1].time);
    const fromDate = new Date(lastDate);

    if (tf === '1Y') fromDate.setFullYear(lastDate.getFullYear() - 1);
    if (tf === '2Y') fromDate.setFullYear(lastDate.getFullYear() - 2);
    if (tf === '5Y') fromDate.setFullYear(lastDate.getFullYear() - 5);

    const fromStr = fromDate.toISOString().split('T')[0];
    const toStr = lastDate.toISOString().split('T')[0];

    try {
      chart.timeScale().setVisibleRange({
        from: fromStr,
        to: toStr,
      });
    } catch {
      chart.timeScale().fitContent();
    }
  };

  return (
    <div className="w-full rounded border border-[#1C2331] bg-[#090C10] overflow-hidden">
      {/* Chart Top Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 border-b border-[#1C2331] bg-[#0C1017] text-xs font-mono select-none">
        {/* Technical Indicator Toggles */}
        <div className="flex items-center gap-3">
          <span className="text-gray-500 font-semibold uppercase text-[10px]">Overlays:</span>

          <button
            onClick={() => setShowShortSma(!showShortSma)}
            className={`flex items-center gap-1.5 px-2 py-0.5 rounded border transition-colors ${
              showShortSma
                ? 'bg-cyan-950/60 border-cyan-500/50 text-cyan-300 font-semibold'
                : 'bg-[#121620] border-[#1C2331] text-gray-400 hover:text-gray-200'
            }`}
          >
            <span className="h-2 w-2 rounded-full bg-cyan-400" />
            <span>SMA {shortWindow}</span>
          </button>

          <button
            onClick={() => setShowLongSma(!showLongSma)}
            className={`flex items-center gap-1.5 px-2 py-0.5 rounded border transition-colors ${
              showLongSma
                ? 'bg-amber-950/60 border-amber-500/50 text-amber-300 font-semibold'
                : 'bg-[#121620] border-[#1C2331] text-gray-400 hover:text-gray-200'
            }`}
          >
            <span className="h-2 w-2 rounded-full bg-amber-400" />
            <span>SMA {longWindow}</span>
          </button>

          {trades.length > 0 && (
            <button
              onClick={() => setShowMarkers(!showMarkers)}
              className={`flex items-center gap-1.5 px-2 py-0.5 rounded border transition-colors ${
                showMarkers
                  ? 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300 font-semibold'
                  : 'bg-[#121620] border-[#1C2331] text-gray-400 hover:text-gray-200'
              }`}
            >
              <span>▲▼ Trade Fills ({trades.length})</span>
            </button>
          )}
        </div>

        {/* Timeframe Presets */}
        <div className="flex items-center gap-1">
          {(['1Y', '2Y', '5Y', 'All'] as const).map((tf) => (
            <button
              key={tf}
              onClick={() => handleTimeframeChange(tf)}
              className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors ${
                selectedTimeframe === tf
                  ? 'bg-cyan-500 text-black font-bold'
                  : 'bg-[#121721] text-gray-400 hover:text-white border border-[#1C2331]'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      <div ref={chartContainerRef} className="w-full" />
    </div>
  );
};
