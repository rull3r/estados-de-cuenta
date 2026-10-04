export function money(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("es-VE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function moneyShort(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(2)} MM`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)} M`;
  return money(value);
}

export function dateLabel(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [year, month, day] = iso.split("-");
  return `${day}/${month}/${year.slice(2)}`;
}

const MONTHS_ES = [
  "Enero",
  "Febrero",
  "Marzo",
  "Abril",
  "Mayo",
  "Junio",
  "Julio",
  "Agosto",
  "Septiembre",
  "Octubre",
  "Noviembre",
  "Diciembre",
];

export function monthName(period: string | null | undefined): string {
  if (!period) return "—";
  const parts = period.split("-");
  if (parts.length !== 3) return period;
  const month = Number(parts[1]);
  const year = parts[2].length === 2 ? `20${parts[2]}` : parts[2];
  return `${MONTHS_ES[month - 1] ?? parts[1]} ${year}`;
}

export function monthShort(period: string | null | undefined): string {
  const full = monthName(period);
  return full.length > 3 ? full.slice(0, 3) : full;
}

export function dayMonthLabel(iso: string | null | undefined): string {
  if (!iso) return "";
  const parts = iso.split("-");
  return parts.length === 3 ? `${parts[2]}/${parts[1]}` : iso;
}

export const STATUS_LABEL: Record<string, string> = {
  CUADRA: "cuadra al céntimo",
  DIFERENCIAS: "con diferencias",
  REVISAR: "revisar",
  procesando: "procesando",
  error: "error",
};

export const METHOD_LABEL: Record<string, string> = {
  transferencia_recibida: "transferencia recibida",
  transferencia_enviada: "transferencia enviada",
  credito_inmediato: "crédito inmediato",
  pago_movil: "pago móvil",
  comision_pago_movil: "comisión pago móvil",
  comision_credito_inmediato: "comisión crédito inmediato",
  comision: "comisión",
  punto_de_venta: "punto de venta",
  tarjeta_debito: "tarjeta de débito",
  pago_terceros: "pago a terceros",
  pago_servicios: "pago de servicios",
  mantenimiento: "mantenimiento",
  emision_estado: "emisión de estado",
  impuesto: "impuesto",
  cheque: "cheque",
  otro: "otro",
};

export function methodLabel(method: string): string {
  return METHOD_LABEL[method] ?? method.replace(/_/g, " ");
}

export function statusClass(status: string): string {
  if (status === "CUADRA") return "ok";
  if (status === "DIFERENCIAS") return "diff";
  if (status === "error") return "diff";
  return "review";
}

function parseUtc(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const value = iso.endsWith("Z") ? iso : `${iso}Z`;
  const time = Date.parse(value);
  return Number.isNaN(time) ? null : time;
}

export function etaLabel(startedAt: string | null | undefined, percent: number): string {
  const start = parseUtc(startedAt);
  if (start === null || percent < 5 || percent >= 100) return "";
  const elapsed = (Date.now() - start) / 1000;
  if (elapsed <= 0) return "";
  const remaining = Math.max(0, Math.round((elapsed * (100 - percent)) / percent));
  if (remaining < 60) return `~${remaining}s restantes`;
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  return `~${minutes}m ${seconds}s restantes`;
}

export function progressLabel(
  stage: string | null | undefined,
  percent: number,
  startedAt: string | null | undefined,
  queuePosition?: number | null,
): string {
  if (queuePosition) return `en cola · posición ${queuePosition}`;
  const eta = etaLabel(startedAt, percent);
  const base = `${stage ?? "procesando"} · ${percent}%`;
  return eta ? `${base} · ${eta}` : base;
}
