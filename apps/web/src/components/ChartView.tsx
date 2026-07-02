"use client";

import type { CSSProperties } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip
} from "recharts";
import type { ChartSpec } from "@/lib/types";

interface ChartViewProps {
  spec: ChartSpec;
}

interface Datum {
  label: string;
  value: number;
}

export default function ChartView({ spec }: ChartViewProps) {
  const data: Datum[] = spec.labels.map((label, i) => ({
    label: String(label),
    value: Number(spec.values[i] ?? 0)
  }));

  if (data.length === 0) return null;

  const axisTick = { fill: "var(--mut)", fontSize: 11 };
  const primary = "#3b82f6";

  return (
    <figure className="mt-3 rounded-lg border border-line bg-surface2 p-3">
      {spec.title && (
        <figcaption className="mb-2 px-1 text-[13px] font-medium text-ink">
          {spec.title}
        </figcaption>
      )}
      <div style={{ width: "100%", height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          {spec.type === "line" ? (
            <LineChart
              data={data}
              margin={{ top: 6, right: 12, bottom: 4, left: 0 }}
            >
              <CartesianGrid stroke="var(--line2)" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={axisTick}
                stroke="var(--line2)"
                tickLine={false}
              />
              <YAxis
                tick={axisTick}
                stroke="var(--line2)"
                tickLine={false}
                width={44}
                label={
                  spec.y_label
                    ? {
                        value: spec.y_label,
                        angle: -90,
                        position: "insideLeft",
                        fill: "var(--mut)",
                        fontSize: 11,
                        style: { textAnchor: "middle" }
                      }
                    : undefined
                }
              />
              <Tooltip
                cursor={{ stroke: "var(--line2)" }}
                contentStyle={tooltipStyle}
                labelStyle={{ color: "var(--mut)" }}
                itemStyle={{ color: "var(--ink)" }}
              />
              <Line
                type="monotone"
                dataKey="value"
                name={spec.field ?? spec.y_label ?? "value"}
                stroke={primary}
                strokeWidth={2}
                dot={{ r: 2, fill: primary }}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          ) : (
            <BarChart
              data={data}
              margin={{ top: 6, right: 12, bottom: 4, left: 0 }}
            >
              <CartesianGrid stroke="var(--line2)" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={axisTick}
                stroke="var(--line2)"
                tickLine={false}
              />
              <YAxis
                tick={axisTick}
                stroke="var(--line2)"
                tickLine={false}
                width={44}
                label={
                  spec.y_label
                    ? {
                        value: spec.y_label,
                        angle: -90,
                        position: "insideLeft",
                        fill: "var(--mut)",
                        fontSize: 11,
                        style: { textAnchor: "middle" }
                      }
                    : undefined
                }
              />
              <Tooltip
                cursor={{ fill: "rgba(59,130,246,0.08)" }}
                contentStyle={tooltipStyle}
                labelStyle={{ color: "var(--mut)" }}
                itemStyle={{ color: "var(--ink)" }}
              />
              <Bar
                dataKey="value"
                name={spec.field ?? spec.y_label ?? "value"}
                fill={primary}
                radius={[3, 3, 0, 0]}
                maxBarSize={48}
              />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

const tooltipStyle: CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--line2)",
  borderRadius: 8,
  fontFamily: "var(--font-mono), ui-monospace, monospace",
  fontSize: 12
};
