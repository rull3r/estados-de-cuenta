import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Bars, Donut, FlowChart } from "../components/Charts";
import { Upload } from "../components/Upload";
import { useToast } from "../components/Toast";
import {
  STATUS_LABEL,
  dateLabel,
  dayMonthLabel,
  methodLabel,
  money,
  moneyShort,
  monthName,
  monthShort,
  statusClass,
} from "../format";
import type { DuplicateGroup, Operation, Statement, Summary } from "../types";

function Delta({
  current,
  previous,
  goodWhenUp,
}: {
  current: number;
  previous: number | null;
  goodWhenUp: boolean;
}) {
  if (previous === null || previous === 0) return null;
  const change = ((current - previous) / Math.abs(previous)) * 100;
  const up = change >= 0;
  const good = up === goodWhenUp;
  return (
    <div className={`delta ${good ? "good" : "bad"}`}>
      {up ? "▲" : "▼"} {Math.abs(change).toFixed(1)}% vs mes anterior
    </div>
  );
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
    const timer = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(timer);
  }, [processing, load]);

  const selected = scope === "all" ? null : statements.find((s) => String(s.id) === scope) ?? null;
  const monthly = summary?.monthly ?? [];
  const selectedIndex = selected ? monthly.findIndex((m) => m.statement_id === selected.id) : -1;
  const previous = selectedIndex > 0 ? monthly[selectedIndex - 1] : null;

  const savingsRate =
    summary && summary.total_abono > 0 ? (summary.net / summary.total_abono) * 100 : 0;
  const latest = statements[0] ?? null;
  const saldoFinal = selected?.saldo_final ?? latest?.saldo_final ?? null;

  const flowPoints =
    selected && summary
      ? summary.by_day.map((day) => ({
          label: dayMonthLabel(day.date),
          cargo: day.cargo,
          abono: day.abono,
          balance: day.balance,
        }))
      : monthly.map((month) => ({
          label: monthShort(month.period_start),
          cargo: month.cargo,
          abono: month.abono,
          balance: month.saldo_final,
        }));

  const categoryItems = (() => {
    if (!summary) return [];
    const rows = [...summary.by_category]
      .filter((row) => row.cargo > 0)
      .sort((a, b) => b.cargo - a.cargo);
    const top = rows.slice(0, 6).map((row) => ({ label: row.label, value: row.cargo }));
    const rest = rows.slice(6).reduce((sum, row) => sum + row.cargo, 0);
    if (rest > 0) top.push({ label: "Otras", value: rest });
    return top;
  })();

  return (
    <>
      <div className="panel">
        <h2 className="panel-title">subir estados de cuenta</h2>
        <Upload onFinished={() => void load()} />
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2 className="panel-title">resumen contable</h2>
          <label className="field scope-field">
            <span>período analizado</span>
            <select value={scope} onChange={(event) => setScope(event.target.value)}>
              <option value="all">Todos los meses ({statements.length} estados)</option>
              {statements.map((statement) => (
                <option key={statement.id} value={statement.id}>
                  {monthName(statement.period_start)} · {statement.period_start} al {statement.period_end}
                </option>
              ))}
            </select>
          </label>
        </div>

        {summary ? (
          <>
            <div className="grid-4">
              <div className="kpi">
                <div className="kpi-label">abonos</div>
                <div className="kpi-value amber">{money(summary.total_abono)}</div>
                <Delta
                  current={summary.total_abono}
                  previous={previous?.abono ?? null}
                  goodWhenUp={true}
                />
                <div className="kpi-sub">{summary.count} movimientos</div>
              </div>
              <div className="kpi">
                <div className="kpi-label">cargos</div>
                <div className="kpi-value danger">{money(summary.total_cargo)}</div>
                <Delta
                  current={summary.total_cargo}
                  previous={previous?.cargo ?? null}
                  goodWhenUp={false}
                />
                <div className="kpi-sub">igtf {money(summary.total_igtf)}</div>
              </div>
              <div className="kpi">
                <div className="kpi-label">resultado neto</div>
                <div className="kpi-value cyan">{money(summary.net)}</div>
                <Delta
                  current={summary.net}
                  previous={
                    previous ? previous.abono - previous.cargo : null
                  }
                  goodWhenUp={true}
                />
                <div className="kpi-sub">
                  ajustes: +{money(summary.adjustments.abono)} / −{money(summary.adjustments.cargo)}
                </div>
              </div>
              <div className="kpi">
                <div className="kpi-label">tasa de ahorro</div>
                <div className="kpi-value">{savingsRate.toFixed(1)}%</div>
                <div className="kpi-sub">
                  de cada 100 que entran, {savingsRate.toFixed(0)} quedan
                </div>
              </div>
            </div>
            <div className="grid-4" style={{ marginTop: 1 }}>
              <div className="kpi">
                <div className="kpi-label">saldo {selected ? "al cierre del mes" : "actual"}</div>
                <div className="kpi-value">{money(saldoFinal)}</div>
                <div className="kpi-sub">
                  {selected ? selected.period_end : latest ? latest.period_end : "—"}
                </div>
              </div>
              <div className="kpi">
                <div className="kpi-label">costos bancarios</div>
                <div className="kpi-value danger">{money(summary.bank_costs.total)}</div>
                <div className="kpi-sub">comisiones, mantenimiento e IGTF</div>
              </div>
              <div className="kpi">
                <div className="kpi-label">ticket promedio</div>
                <div className="kpi-value">{money(summary.averages.ticket)}</div>
                <div className="kpi-sub">
                  mayor cargo {moneyShort(summary.averages.max_cargo)} · mayor abono{" "}
                  {moneyShort(summary.averages.max_abono)}
                </div>
              </div>
              <div className="kpi">
                <div className="kpi-label">promedio diario</div>
                <div className="kpi-value">
                  <span className="num-cargo">−{moneyShort(summary.averages.daily_cargo)}</span>{" "}
                  <span className="num-abono">+{moneyShort(summary.averages.daily_abono)}</span>
                </div>
                <div className="kpi-sub">{summary.averages.days} días con actividad</div>
              </div>
            </div>
          </>
        ) : (
          <p className="muted">Cargando…</p>
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2 className="panel-title">
            flujo {selected ? "diario del mes" : "mensual"}
          </h2>
          <div className="legend">
            <span>
              <i className="swatch cargo" /> cargos
            </span>
            <span>
              <i className="swatch abono" /> abonos
            </span>
            <span>
              <i className="swatch saldo" /> saldo
            </span>
          </div>
        </div>
        <FlowChart points={flowPoints} />
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2 className="panel-title">categorías con más cargos</h2>
          <Donut items={categoryItems} centerLabel="cargos" />
        </div>
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
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2 className="panel-title">a quién le pagas más</h2>
          <Bars
            items={
              summary
                ? summary.top_counterparts.cargo.map((row) => ({
                    label: row.label,
                    value: row.total,
                    hint: moneyShort(row.total),
                  }))
                : []
            }
            emptyText="Sin cargos con contraparte identificada."
          />
        </div>
        <div className="panel">
          <h2 className="panel-title">de quién recibes más</h2>
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
          <h2 className="panel-title">comportamiento por día de la semana</h2>
          <Bars
            items={
              summary
                ? summary.by_weekday.map((row) => ({
                    label: row.label,
                    value: row.cargo,
                    hint: moneyShort(row.cargo),
                  }))
                : []
            }
            emptyText="Sin datos de días."
          />
          <p className="panel-note" style={{ marginTop: 8 }}>
            Total de cargos según el día en que ocurrió la operación.
          </p>
        </div>
        <div className="panel">
          <h2 className="panel-title">días con más gasto</h2>
          <div className="table-wrap" style={{ maxHeight: 260 }}>
            <table className="grid-table">
              <thead>
                <tr>
                  <th>fecha</th>
                  <th className="num">cargos</th>
                  <th className="num">movs</th>
                </tr>
              </thead>
              <tbody>
                {(summary?.top_days ?? []).map((day) => (
                  <tr key={day.date}>
                    <td className="mono">{dateLabel(day.date)}</td>
                    <td className="num num-cargo">{money(day.cargo)}</td>
                    <td className="num">{day.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
                    <td>
                      {group.reference ??
                        (group.counterpart_account ? `***${group.counterpart_account}` : "—")}
                    </td>
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
                  <th>período</th>
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
                        {monthName(statement.period_start)}
                      </Link>
                      <div className="muted" style={{ fontSize: 10 }}>
                        {statement.period_start} al {statement.period_end}
                      </div>
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
