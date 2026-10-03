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
