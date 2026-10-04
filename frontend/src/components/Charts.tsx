import { money, moneyShort } from "../format";

interface Point {
  label: string;
  value: number | null;
}

export function Sparkline({ points }: { points: Point[] }) {
  const values = points.map((point) => point.value ?? 0);
  if (values.length < 2) {
    return <p className="muted">Se necesitan al menos dos estados de cuenta para dibujar la evolución.</p>;
  }
  const width = 720;
  const height = 190;
  const pad = 18;
  const bottom = 46;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = (width - pad * 2) / (values.length - 1);
  const coords = values.map((value, index) => ({
    x: pad + index * stepX,
    y: height - bottom - ((value - min) / span) * (height - pad - bottom),
  }));
  const path = coords
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(1)},${point.y.toFixed(1)}`)
    .join(" ");
  // Con muchos meses se muestran ~12 etiquetas y se inclinan para que no se pisen.
  const labelStep = Math.max(1, Math.ceil(points.length / 12));
  const labelY = height - 8;
  return (
    <svg className="spark" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Evolución del saldo final">
      {[0.25, 0.5, 0.75].map((fraction) => (
        <line
          key={fraction}
          x1={pad}
          x2={width - pad}
          y1={pad + fraction * (height - pad - bottom)}
          y2={pad + fraction * (height - pad - bottom)}
          stroke="#1e2c33"
          strokeWidth="1"
        />
      ))}
      <path d={path} fill="none" stroke="#ffb454" strokeWidth="1.6" />
      {coords.map((point, index) => (
        <circle key={index} cx={point.x} cy={point.y} r="2.6" fill="#0b0f12" stroke="#ffb454" strokeWidth="1.4" />
      ))}
      {points.map((point, index) =>
        index % labelStep === 0 || index === points.length - 1 ? (
          <text
            key={point.label}
            x={coords[index].x + 3}
            y={labelY}
            textAnchor="end"
            transform={`rotate(-40 ${coords[index].x + 3} ${labelY})`}
          >
            {point.label}
          </text>
        ) : null,
      )}
      <text x={pad} y={pad - 4}>
        {moneyShort(max)}
      </text>
      <text x={pad} y={height - bottom + 12}>
        {moneyShort(min)}
      </text>
    </svg>
  );
}

interface BarItem {
  label: string;
  value: number;
  hint?: string;
}

export function Bars({ items, emptyText }: { items: BarItem[]; emptyText?: string }) {
  if (items.length === 0) {
    return <p className="muted">{emptyText ?? "Sin datos todavía."}</p>;
  }
  const max = Math.max(...items.map((item) => item.value)) || 1;
  return (
    <div className="bars">
      {items.map((item) => (
        <div className="bar-row" key={item.label}>
          <span title={item.label}>{item.label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${Math.max(2, (item.value / max) * 100)}%` }} />
          </div>
          <span className="bar-value">{item.hint ?? money(item.value)}</span>
        </div>
      ))}
    </div>
  );
}

export interface FlowPoint {
  label: string;
  cargo: number;
  abono: number;
  balance: number | null;
}

export function FlowChart({ points }: { points: FlowPoint[] }) {
  if (points.length === 0) {
    return <p className="muted">Sin datos para graficar.</p>;
  }
  const width = 760;
  const height = 250;
  const padL = 16;
  const padR = 16;
  const padT = 26;
  const padB = 58;
  const plotH = height - padT - padB;
  const maxFlow = Math.max(...points.map((point) => Math.max(point.cargo, point.abono)), 1);
  const balances = points
    .map((point) => point.balance)
    .filter((value): value is number => value !== null && value !== undefined);
  const minBal = balances.length ? Math.min(...balances) : 0;
  const maxBal = balances.length ? Math.max(...balances) : 1;
  const balSpan = maxBal - minBal || 1;
  const step = (width - padL - padR) / points.length;
  const barW = Math.max(1.5, Math.min(9, step * 0.3));
  const yFlow = (value: number) => padT + plotH - (value / maxFlow) * plotH;
  const yBal = (value: number) => padT + plotH - ((value - minBal) / balSpan) * plotH;
  const labelStep = Math.max(1, Math.ceil(points.length / 14));
  const labelY = height - 10;

  const pathParts: string[] = [];
  points.forEach((point, index) => {
    if (point.balance === null || point.balance === undefined) return;
    const x = padL + step * index + step / 2;
    pathParts.push(`${pathParts.length ? "L" : "M"}${x.toFixed(1)},${yBal(point.balance).toFixed(1)}`);
  });

  return (
    <svg className="flow" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Flujo del período">
      {[0, 0.25, 0.5, 0.75, 1].map((fraction) => (
        <line
          key={fraction}
          x1={padL}
          x2={width - padR}
          y1={padT + fraction * plotH}
          y2={padT + fraction * plotH}
          stroke="#1e2c33"
          strokeWidth="1"
        />
      ))}
      {points.map((point, index) => {
        const x = padL + step * index + step / 2;
        const cargoHeight = Math.max(0, padT + plotH - yFlow(point.cargo));
        const abonoHeight = Math.max(0, padT + plotH - yFlow(point.abono));
        return (
          <g key={index}>
            <rect
              x={x - barW - 1}
              y={yFlow(point.cargo)}
              width={barW}
              height={cargoHeight}
              fill="#ff6b5a"
              opacity="0.85"
            />
            <rect
              x={x + 1}
              y={yFlow(point.abono)}
              width={barW}
              height={abonoHeight}
              fill="#9ad98f"
              opacity="0.85"
            />
          </g>
        );
      })}
      {pathParts.length > 1 && (
        <path d={pathParts.join(" ")} fill="none" stroke="#7fc8be" strokeWidth="1.8" />
      )}
      {points.map((point, index) =>
        index % labelStep === 0 || index === points.length - 1 ? (
          <text
            key={index}
            x={padL + step * index + step / 2 + 3}
            y={labelY}
            textAnchor="end"
            transform={`rotate(-40 ${padL + step * index + step / 2 + 3} ${labelY})`}
          >
            {point.label}
          </text>
        ) : null,
      )}
      <text x={padL} y={padT - 10}>
        {moneyShort(maxFlow)}
      </text>
      {balances.length > 0 && (
        <text x={width - padR} y={padT - 10} textAnchor="end">
          saldo {moneyShort(maxBal)}
        </text>
      )}
    </svg>
  );
}

const DONUT_COLORS = [
  "#ffb454",
  "#7fc8be",
  "#ff6b5a",
  "#9ad98f",
  "#c9a0ff",
  "#6fa8dc",
  "#e0c56e",
  "#b0bec5",
];

export function Donut({
  items,
  centerLabel,
}: {
  items: { label: string; value: number }[];
  centerLabel?: string;
}) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  if (total <= 0) {
    return <p className="muted">Sin datos.</p>;
  }
  const radius = 56;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 160 160" className="donut">
        <g transform="translate(80,80) rotate(-90)">
          {items.map((item, index) => {
            const fraction = item.value / total;
            const dash = fraction * circumference;
            const segment = (
              <circle
                key={item.label}
                r={radius}
                fill="none"
                stroke={DONUT_COLORS[index % DONUT_COLORS.length]}
                strokeWidth="18"
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offset}
              />
            );
            offset += dash;
            return segment;
          })}
        </g>
        <text x="80" y="78" textAnchor="middle" className="donut-total">
          {moneyShort(total)}
        </text>
        <text x="80" y="94" textAnchor="middle" className="donut-sub">
          {centerLabel ?? "total"}
        </text>
      </svg>
      <ul className="donut-legend">
        {items.map((item, index) => (
          <li key={item.label}>
            <span className="dot" style={{ background: DONUT_COLORS[index % DONUT_COLORS.length] }} />
            <span className="donut-name">{item.label}</span>
            <span className="muted">{Math.round((100 * item.value) / total)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
