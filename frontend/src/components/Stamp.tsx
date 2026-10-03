export function Stamp({ status, label }: { status: string; label?: string }) {
  const ok = status === "CUADRA";
  const big = ok ? "CUADRA" : status === "DIFERENCIAS" ? "DIFERENCIAS" : status.toUpperCase();
  return (
    <div className={`stamp ${ok ? "" : "diff"}`} role="img" aria-label={`Estado: ${big}`}>
      <span className="big">{big}</span>
      <span className="small">{ok ? "AL CÉNTIMO" : label ?? "DETECTADAS"}</span>
    </div>
  );
}
