import React, { useEffect, useRef } from 'react';
import { AreaSeries, ColorType, createChart } from 'lightweight-charts';
import type { EquityPoint } from '../../types/api';

interface DrawdownChartProps {
  equityCurve: EquityPoint[];
  colorblindMode: boolean;
  height?: number;
}

export const DrawdownChart: React.FC<DrawdownChartProps> = ({
  equityCurve,
  colorblindMode,
  height = 180,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current || equityCurve.length === 0) return;

    const lineColor = colorblindMode ? '#D97706' : '#F43F5E';
    const topColor = 'rgba(244, 63, 94, 0.0)';
    const bottomColor = colorblindMode ? 'rgba(217, 119, 6, 0.35)' : 'rgba(244, 63, 94, 0.35)';

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#090C10' },
        textColor: '#8E9BAE',
      },
      grid: {
        vertLines: { color: '#141A24' },
        horzLines: { color: '#141A24' },
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
      lineWidth: 1,
      priceFormat: {
        type: 'custom',
        formatter: (val: number) => `${val.toFixed(1)}%`,
      },
    });

    const ddData = equityCurve.map((pt) => ({
      time: pt.time,
      value: pt.drawdown,
    }));
    areaSeries.setData(ddData);

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
