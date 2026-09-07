import React, { useEffect, useRef } from 'react';
import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
} from 'lightweight-charts';
import type { BarData } from '../../types/api';

interface CandlestickChartProps {
  data: BarData[];
  colorblindMode: boolean;
  height?: number;
}

export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  data,
  colorblindMode,
  height = 450,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);

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
    };
  }, [data, colorblindMode, height]);

  return (
    <div className="w-full relative rounded border border-[#1C2331] bg-[#090C10] overflow-hidden">
      <div ref={chartContainerRef} className="w-full" />
    </div>
  );
};
