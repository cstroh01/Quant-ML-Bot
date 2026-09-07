import React, { useEffect, useRef } from 'react';
import { AreaSeries, ColorType, createChart } from 'lightweight-charts';
import type { EquityPoint } from '../../types/api';

interface EquityCurveChartProps {
  equityCurve: EquityPoint[];
  colorblindMode: boolean;
  height?: number;
}

export const EquityCurveChart: React.FC<EquityCurveChartProps> = ({
  equityCurve,
  colorblindMode,
  height = 360,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current || equityCurve.length === 0) return;

    const lineColor = colorblindMode ? '#0284C7' : '#10B981';
    const topColor = colorblindMode ? 'rgba(2, 132, 199, 0.28)' : 'rgba(16, 185, 129, 0.28)';
    const bottomColor = 'rgba(16, 185, 129, 0.0)';

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

    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor,
      topColor,
      bottomColor,
      lineWidth: 2,
      priceFormat: {
        type: 'price',
        precision: 2,
        minMove: 0.01,
      },
    });

    const curveData = equityCurve.map((pt) => ({
      time: pt.time,
      value: pt.equity,
    }));
    areaSeries.setData(curveData);

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
  }, [equityCurve, colorblindMode, height]);

  return (
    <div className="w-full relative rounded border border-[#1C2331] bg-[#090C10] overflow-hidden">
      <div ref={chartContainerRef} className="w-full" />
    </div>
  );
};
