import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Bars, Sparkline } from "../components/Charts";
import { Upload } from "../components/Upload";
import { useToast } from "../components/Toast";
import { STATUS_LABEL, dateLabel, money, moneyShort, methodLabel, statusClass } from "../format";
import type { Operation, Statement, Summary } from "../types";

function monthShort(period: string | null): string {
  if (!period) return "—";
  const parts = period.split("-");
  const names = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const month = Number(parts[1]) - 1;
  return names[month] ?? period;
}

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [statements, setStatements] = useState<Statement[]>([]);
  const [biggest, setBiggest] = useState<Operation[]>([]);
  const [scope, setScope] = useState<string>("all");
  const notify = useToast();

  const load = useCallback(async () => {
    try {
      const statementId = scope === "all" ? undefined : Number(scope);
      const [nextSummary, nextStatements, nextBiggest] = await Promise.all([
        api.summary(statementId),
        api.statements(),
        api.biggest(statementId),
      ]);
      setSummary(nextSummary);
      setStatements(nextStatements);
      setBiggest(nextBiggest);
    } catch (error) {
      notify(error instanceof Error ? error.message : "No se pudieron cargar los datos", "error");
    }
  }, [scope, notify]);

  useEffect(() => {
    void load();
  }, [load]);

  function pollStatement(id: number) {
    const timer = window.setInterval(async () => {
      try {
        const statement = await api.statement(id);
        if (statement.status !== "procesando") {
          window.clearInterval(timer);
          await load();
          if (statement.status === "CUADRA") {
            notify(`Conciliación perfecta: ${statement.file_name} cuadra al céntimo.`);
          } else if (statement.status === "error") {
            notify(`Error al procesar ${statement.file_name}: ${statement.error}`, "error");
          } else {
            notify(`${statement.file_name}: ${STATUS_LABEL[statement.status] ?? statement.status}.`);
          }
        }
      } catch {
        window.clearInterval(timer);
      }
    }, 2500);
    window.setTimeout(() => window.clearInterval(timer), 10 * 60 * 1000);
  }

  const processing = statements.some((statement) => statement.status === "procesando");
  useEffect(() => {
    if (!processing) return;
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
  }, [processing, load]);

  return (
    <>
      <div className="panel">
        <h2 className="panel-title">subir estado de cuenta</h2>
        <Upload
          onUploaded={(id) => {
            pollStatement(id);
            void load();
          }}
        />
      </div>

      <div className="panel">
        <h2 className="panel-title">resumen</h2>
        <div className="filters" style={{ marginBottom: 14 }}>
          <label className="field">
            <span>alcance</span>
            <select value={scope} onChange={(event) => setScope(event.target.value)}>
              <option value="all">todos los meses</option>
              {statements.map((statement) => (
                <option key={statement.id} value={statement.id}>
                  {statement.period_start} → {statement.period_end}
                </option>
              ))}
            </select>
          </label>
        </div>
        {summary ? (
          <div className="grid-4">
            <div className="kpi">
              <div className="kpi-label">abonos</div>
              <div className="kpi-value amber">{money(summary.total_abono)}</div>
              <div className="kpi-sub">{summary.count} movimientos en total</div>
            </div>
            <div className="kpi">
              <div className="kpi-label">cargos</div>
              <div className="kpi-value danger">{money(summary.total_cargo)}</div>
              <div className="kpi-sub">igtf {money(summary.total_igtf)}</div>
            </div>
            <div className="kpi">
              <div className="kpi-label">neto</div>
              <div className="kpi-value cyan">{money(summary.net)}</div>
              <div className="kpi-sub">
                ajustes: +{money(summary.adjustments.abono)} / −{money(summary.adjustments.cargo)}
              </div>
            </div>
            <div className="kpi">
              <div className="kpi-label">estados</div>
              <div className="kpi-value">{statements.length}</div>
              <div className="kpi-sub">
                {statements.filter((statement) => statement.status === "CUADRA").length} cuadran al céntimo
              </div>
            </div>
          </div>
        ) : (
          <p className="muted">Cargando…</p>
        )}
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2 className="panel-title">evolución del saldo final</h2>
          {summary && summary.monthly.length > 0 ? (
            <Sparkline
              points={summary.monthly.map((month) => ({
                label: `${monthShort(month.period_start)} ${month.period_end?.slice(-2) ?? ""}`,
                value: month.saldo_final,
              }))}
            />
          ) : (
            <p className="muted">Sube tu primer estado de cuenta para ver la evolución.</p>
          )}
        </div>
        <div className="panel">
          <h2 className="panel-title">categorías con más cargos</h2>
          <Bars
            items={
              summary
                ? [...summary.by_category]
                    .filter((row) => row.cargo > 0)
                    .sort((a, b) => b.cargo - a.cargo)
                    .slice(0, 8)
                    .map((row) => ({ label: row.label, value: row.cargo, hint: moneyShort(row.cargo) }))
                : []
            }
            emptyText="Sin cargos registrados."
          />
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2 className="panel-title">métodos de pago más usados</h2>
          <Bars
            items={
              summary
                ? [...summary.by_method]
                    .sort((a, b) => b.count - a.count)
                    .slice(0, 8)
                    .map((row) => ({
                      label: methodLabel(row.label),
                      value: row.count,
                      hint: `${row.count} ops`,
                    }))
                : []
            }
          />
        </div>
        <div className="panel">
          <h2 className="panel-title">contrapartes top (abonos)</h2>
          <Bars
            items={
              summary
                ? summary.top_counterparts.abono.map((row) => ({
                    label: row.label,
                    value: row.total,
                    hint: moneyShort(row.total),
                  }))
                : []
            }
            emptyText="Sin abonos con contraparte identificada."
          />
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2 className="panel-title">mayores movimientos</h2>
          <div className="table-wrap" style={{ maxHeight: 320 }}>
            <table className="grid-table">
              <thead>
                <tr>
                  <th>fecha</th>
                  <th>descripción</th>
                  <th className="num">monto</th>
                </tr>
              </thead>
              <tbody>
                {biggest.map((operation) => (
                  <tr key={operation.id}>
                    <td>{dateLabel(operation.date_iso)}</td>
                    <td className="desc">{operation.description.slice(0, 90)}</td>
                    <td className="num">{money(operation.amount)}</td>
                  </tr>
                ))}
                {biggest.length === 0 && (
                  <tr>
                    <td colSpan={3} className="muted">
                      Sin datos.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
        <div className="panel">
          <h2 className="panel-title">últimos estados</h2>
          <div className="table-wrap" style={{ maxHeight: 320 }}>
            <table className="grid-table">
              <thead>
                <tr>
                  <th>periodo</th>
                  <th className="num">abonos</th>
                  <th className="num">cargos</th>
                  <th>estado</th>
                </tr>
              </thead>
              <tbody>
                {[...statements]
                  .sort((a, b) => (b.period_start ?? "").localeCompare(a.period_start ?? ""))
                  .slice(0, 8)
                  .map((statement) => (
                    <tr key={statement.id}>
                      <td>
                        <Link className="plain" to={`/estados/${statement.id}`}>
                          {statement.period_start} → {statement.period_end}
                        </Link>
                      </td>
                      <td className="num num-abono">{moneyShort(statement.total_abono)}</td>
                      <td className="num num-cargo">{moneyShort(statement.total_cargo)}</td>
                      <td>
                        <span className={`badge ${statusClass(statement.status)}`}>
                          {STATUS_LABEL[statement.status] ?? statement.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                {statements.length === 0 && (
                  <tr>
                    <td colSpan={4} className="muted">
                      Todavía no hay estados de cuenta.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}
