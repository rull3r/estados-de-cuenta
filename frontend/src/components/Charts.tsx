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
