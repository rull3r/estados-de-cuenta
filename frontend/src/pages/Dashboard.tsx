import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Bars, Sparkline } from "../components/Charts";
import { Upload } from "../components/Upload";
import { useToast } from "../components/Toast";
import { STATUS_LABEL, dateLabel, money, moneyShort, methodLabel, statusClass } from "../format";
import type { DuplicateGroup, Operation, Statement, Summary } from "../types";

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
  const [duplicates, setDuplicates] = useState<DuplicateGroup[]>([]);
  const [scope, setScope] = useState<string>("all");
  const notify = useToast();

  const load = useCallback(async () => {
    try {
      const statementId = scope === "all" ? undefined : Number(scope);
      const [nextSummary, nextStatements, nextBiggest, nextDuplicates] = await Promise.all([
        api.summary(statementId),
        api.statements(),
        api.biggest(statementId),
        api.duplicates(),
      ]);
      setSummary(nextSummary);
      setStatements(nextStatements);
      setBiggest(nextBiggest);
      setDuplicates(nextDuplicates);
    } catch (error) {
      notify(error instanceof Error ? error.message : "No se pudieron cargar los datos", "error");
    }
  }, [scope, notify]);

  useEffect(() => {
    void load();
  }, [load]);

  const processing = statements.some((statement) => statement.status === "procesando");
  useEffect(() => {
    if (!processing) return;
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
  }, [processing, load]);

  return (
    <>
      <div className="panel">
        <h2 className="panel-title">subir estados de cuenta</h2>
        <Upload onFinished={() => void load()} />
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

      <div className="panel">
        <h2 className="panel-title">
          operaciones repetidas entre estados {duplicates.length ? `· ${duplicates.length}` : ""}
        </h2>
        {duplicates.length === 0 ? (
          <p className="muted">
            Sin repetidas detectadas. Si dos estados comparten período, o el banco repite una operación del
            mes anterior, aparecerá aquí con los archivos donde está.
          </p>
        ) : (
          <div className="table-wrap" style={{ maxHeight: 320 }}>
            <table className="grid-table">
              <thead>
                <tr>
                  <th>fecha</th>
                  <th className="num">monto</th>
                  <th>sentido</th>
                  <th>referencia</th>
                  <th className="num">estados</th>
                  <th>dónde aparece</th>
                </tr>
              </thead>
              <tbody>
                {duplicates.map((group, index) => (
                  <tr key={`${group.date_iso}-${group.amount}-${index}`}>
                    <td className="mono">{dateLabel(group.date_iso)}</td>
                    <td className="num">{money(group.amount)}</td>
                    <td>{group.direction === "abono" ? "abono" : "cargo"}</td>
                    <td>{group.reference ?? (group.counterpart_account ? `***${group.counterpart_account}` : "—")}</td>
                    <td className="num">{group.statement_count}</td>
                    <td className="desc">
                      {group.operations
                        .map(
                          (operation) =>
                            `${operation.statement_file}: ${operation.description.slice(0, 55)}`,
                        )
                        .join(" · ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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
                {statements.slice(0, 8).map((statement) => (
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
