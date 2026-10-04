import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { Stamp } from "../components/Stamp";
import { useToast } from "../components/Toast";
import { STATUS_LABEL, money, statusClass } from "../format";
import type { Statement } from "../types";

function CheckLine({
  label,
  parsed,
  expected,
}: {
  label: string;
  parsed: number | null;
  expected: number | null;
}) {
  const ok = parsed !== null && expected !== null && Math.abs(parsed - expected) < 0.005;
  const delta = parsed !== null && expected !== null ? parsed - expected : null;
  return (
    <div className="check">
      <span className={`mark ${ok ? "" : "bad"}`}>{ok ? "OK" : "Δ"}</span>
      <span>
        {label}: libro <strong className="mono">{money(parsed)}</strong> · resumen{" "}
        <strong className="mono">{money(expected)}</strong>
        {!ok && delta !== null ? ` · diferencia ${money(delta)}` : ""}
      </span>
    </div>
  );
}

export default function StatementDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const notify = useToast();
  const [statement, setStatement] = useState<Statement | null>(null);
  const [form, setForm] = useState({ date: "", description: "", amount: "", note: "" });
  const [direction, setDirection] = useState<"cargo" | "abono">("cargo");

  const load = useCallback(async () => {
    if (!id) return;
    try {
      setStatement(await api.statement(Number(id)));
    } catch (error) {
      notify(error instanceof Error ? error.message : "No se pudo cargar", "error");
    }
  }, [id, notify]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (statement?.status !== "procesando") return;
    const timer = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(timer);
  }, [statement, load]);

  if (!statement) {
    return <p className="muted">Cargando peritaje…</p>;
  }

  const report = statement.report;
  const missing = statement.issues?.filter((issue) => issue.kind === "fila_omitida") ?? [];
  const differences =
    statement.issues?.filter((issue) => issue.kind !== "fila_omitida" && issue.kind !== "advertencia") ?? [];
  const warnings = statement.issues?.filter((issue) => issue.kind === "advertencia") ?? [];

  async function addAdjustment() {
    if (!id) return;
    const amount = Number(form.amount.replace(",", "."));
    if (!form.date || !form.description || !amount || amount <= 0) {
      notify("Completa fecha, descripción y monto del ajuste.", "error");
      return;
    }
    try {
      await api.addAdjustment(Number(id), {
        date: form.date,
        description: form.description,
        amount,
        direction,
        note: form.note || undefined,
      });
      setForm({ date: "", description: "", amount: "", note: "" });
      notify("Ajuste registrado. Las estadísticas ahora pueden cuadrar con el banco.");
      await load();
    } catch (error) {
      notify(error instanceof Error ? error.message : "No se pudo guardar el ajuste", "error");
    }
  }

  return (
    <>
      <div className="panel">
        <div className="detail-head">
          <div>
            <h2 className="panel-title">peritaje del estado de cuenta</h2>
            <div className="kv">
              <div>
                <span>archivo</span>
                {statement.file_name}
              </div>
              <div>
                <span>período</span>
                {statement.period_start} → {statement.period_end}
              </div>
              <div>
                <span>cuenta</span>
                {statement.account_number ?? "—"}
              </div>
              <div>
                <span>titular</span>
                {statement.holder ?? "—"}
              </div>
              <div>
                <span>páginas</span>
                {statement.pages}
              </div>
              <div>
                <span>movimientos</span>
                {statement.transaction_count} · anexo {statement.annex_count} · pos {statement.pos_count}
              </div>
            </div>
            <div style={{ marginTop: 10 }}>
              <span className={`badge ${statusClass(statement.status)}`}>
                {STATUS_LABEL[statement.status] ?? statement.status}
              </span>
            </div>
          </div>
          {statement.status !== "procesando" && (
            <Stamp status={statement.status} label={missing.length ? "FILAS OMITIDAS" : undefined} />
          )}
        </div>
      </div>

      {statement.status === "error" && (
        <div className="panel">
          <div className="issue">Error de lectura: {statement.error}</div>
        </div>
      )}

      {statement.status === "procesando" && (
        <div className="panel">
          <p className="muted">Leyendo el PDF y conciliando contra el resumen oficial…</p>
        </div>
      )}

      {report && (
        <div className="panel">
          <h2 className="panel-title">conciliación contra el resumen del banco</h2>
          <div className="checks">
            <CheckLine label="abonos" parsed={statement.total_abono} expected={report.expected_abono} />
            <CheckLine label="cargos" parsed={statement.total_cargo} expected={report.expected_cargo} />
            <CheckLine label="neto" parsed={report.computed_net} expected={report.expected_net} />
            <div className="check">
              <span className="mark">·</span>
              <span>
                saldo: {money(statement.saldo_inicio)} → {money(statement.saldo_final)} · igtf{" "}
                {money(statement.total_igtf)}
              </span>
            </div>
          </div>
        </div>
      )}

      {(missing.length > 0 || differences.length > 0 || warnings.length > 0) && (
        <div className="panel">
          <h2 className="panel-title">incidencias detectadas</h2>
          {missing.map((issue) => (
            <div className="issue" key={issue.id}>
              <strong>fila omitida por el banco</strong> · {issue.detail}
            </div>
          ))}
          {differences.map((issue) => (
            <div className="issue" key={issue.id}>
              {issue.detail}
              {issue.expected !== null && issue.parsed !== null
                ? ` · esperado ${money(issue.expected)} / leído ${money(issue.parsed)}`
                : ""}
            </div>
          ))}
          {warnings.map((issue) => (
            <div className="issue warn" key={issue.id}>
              {issue.detail}
            </div>
          ))}
        </div>
      )}

      {report && report.checkpoints.length > 0 && (
        <div className="panel">
          <h2 className="panel-title">saldos impresos dentro del libro</h2>
          <div className="table-wrap" style={{ maxHeight: 320 }}>
            <table className="grid-table">
              <thead>
                <tr>
                  <th>pág</th>
                  <th>tipo</th>
                  <th className="num">impreso</th>
                  <th className="num">calculado</th>
                  <th className="num">diferencia</th>
                  <th>detalle</th>
                </tr>
              </thead>
              <tbody>
                {report.checkpoints.map((checkpoint, index) => (
                  <tr key={index}>
                    <td className="mono">{checkpoint.page}</td>
                    <td>{checkpoint.kind}</td>
                    <td className="num">{money(checkpoint.printed)}</td>
                    <td className="num">{money(checkpoint.computed)}</td>
                    <td className="num">{money(checkpoint.difference)}</td>
                    <td className="muted">{checkpoint.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="panel">
        <h2 className="panel-title">ajustes manuales</h2>
        <p className="panel-note" style={{ marginBottom: 12 }}>
          Cuando el banco no imprime una operación, registra aquí el monto deducido del cuadre para que las
          estadísticas coincidan con el saldo oficial. El ajuste queda separado de las filas leídas.
        </p>
        <div className="filters">
          <label className="field">
            <span>fecha (dd/mm)</span>
            <input value={form.date} placeholder="31/01" onChange={(event) => setForm({ ...form, date: event.target.value })} />
          </label>
          <label className="field">
            <span>descripción</span>
            <input
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </label>
          <label className="field">
            <span>monto</span>
            <input value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} />
          </label>
          <label className="field">
            <span>tipo</span>
            <select value={direction} onChange={(event) => setDirection(event.target.value as "cargo" | "abono")}>
              <option value="cargo">cargo</option>
              <option value="abono">abono</option>
            </select>
          </label>
          <button className="btn primary" onClick={() => void addAdjustment()}>
            agregar ajuste
          </button>
        </div>
        {statement.adjustments && statement.adjustments.length > 0 && (
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="grid-table">
              <thead>
                <tr>
                  <th>fecha</th>
                  <th>descripción</th>
                  <th className="num">monto</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {statement.adjustments.map((adjustment) => (
                  <tr key={adjustment.id}>
                    <td>{adjustment.date}</td>
                    <td>{adjustment.description}</td>
                    <td className={`num ${adjustment.direction === "cargo" ? "num-cargo" : "num-abono"}`}>
                      {money(adjustment.amount)}
                    </td>
                    <td>
                      <button
                        className="btn danger"
                        onClick={async () => {
                          await api.deleteAdjustment(statement.id, adjustment.id);
                          await load();
                        }}
                      >
                        quitar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <Link className="btn" to="/estados">
            ◀ volver
          </Link>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button
              className="btn"
              disabled={statement.status === "procesando"}
              onClick={async () => {
                try {
                  await api.reprocessStatement(statement.id);
                  notify("Releyendo el PDF con el motor de extracción actual…");
                  await load();
                } catch (error) {
                  notify(error instanceof Error ? error.message : "No se pudo reprocesar", "error");
                }
              }}
            >
              reprocesar PDF
            </button>
            <button
              className="btn danger"
              onClick={async () => {
                if (!window.confirm("¿Eliminar este estado de cuenta y todos sus movimientos?")) return;
                await api.deleteStatement(statement.id);
                notify("Estado de cuenta eliminado.");
                navigate("/estados");
              }}
            >
              eliminar estado
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
