import { useEffect, useMemo, useState } from "react";
import { api, exportUrl } from "../api";
import { useToast } from "../components/Toast";
import { METHOD_LABEL, dateLabel, methodLabel, money } from "../format";
import type { Operation, OperationPage, Statement } from "../types";

function timeLabel(occurredAt: string | null): string {
  if (!occurredAt) return "";
  const parts = occurredAt.split(" ");
  return parts.length > 1 ? parts[1] : "";
}

export default function Movements() {
  const [statements, setStatements] = useState<Statement[]>([]);
  const [data, setData] = useState<OperationPage | null>(null);
  const [selected, setSelected] = useState<Operation | null>(null);
  const [page, setPage] = useState(1);
  const [text, setText] = useState("");
  const [statementId, setStatementId] = useState("");
  const [direction, setDirection] = useState("");
  const [method, setMethod] = useState("");
  const [category, setCategory] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [sort, setSort] = useState("date");
  const [order, setOrder] = useState("asc");
  const [categories, setCategories] = useState<string[]>([]);
  const notify = useToast();

  useEffect(() => {
    api.statements().then(setStatements).catch(() => undefined);
    api
      .categories()
      .then((response) => setCategories(response.categories))
      .catch(() => undefined);
  }, []);

  const params = useMemo(() => {
    const next = new URLSearchParams();
    if (text) next.set("text", text);
    if (statementId) next.set("statement_id", statementId);
    if (direction) next.set("direction", direction);
    if (method) next.set("method", method);
    if (category) next.set("category", category);
    if (dateFrom) next.set("date_from", dateFrom);
    if (dateTo) next.set("date_to", dateTo);
    if (minAmount) next.set("min_amount", minAmount);
    if (maxAmount) next.set("max_amount", maxAmount);
    next.set("sort", sort);
    next.set("order", order);
    next.set("page", String(page));
    next.set("page_size", "50");
    return next;
  }, [text, statementId, direction, method, category, dateFrom, dateTo, minAmount, maxAmount, sort, order, page]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api
        .operations(params)
        .then(setData)
        .catch((error) => notify(error instanceof Error ? error.message : "Error al buscar", "error"));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [params, notify]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <>
      <div className="panel">
        <h2 className="panel-title">buscar y filtrar</h2>
        <div className="filters">
          <label className="field">
            <span>texto (descripción, contraparte, referencia)</span>
            <input
              value={text}
              placeholder="ej: juan perez, pago movil, 0847…"
              onChange={(event) => {
                setText(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <label className="field">
            <span>estado</span>
            <select
              value={statementId}
              onChange={(event) => {
                setStatementId(event.target.value);
                setPage(1);
              }}
            >
              <option value="">todos</option>
              {statements.map((statement) => (
                <option key={statement.id} value={statement.id}>
                  {statement.period_start} → {statement.period_end}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>tipo</span>
            <select value={direction} onChange={(event) => setDirection(event.target.value)}>
              <option value="">cargos y abonos</option>
              <option value="cargo">solo cargos</option>
              <option value="abono">solo abonos</option>
            </select>
          </label>
          <label className="field">
            <span>método</span>
            <select value={method} onChange={(event) => setMethod(event.target.value)}>
              <option value="">todos</option>
              {Object.entries(METHOD_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>categoría</span>
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">todas</option>
              {categories.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>desde</span>
            <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
          </label>
          <label className="field">
            <span>hasta</span>
            <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
          </label>
          <label className="field">
            <span>monto mín.</span>
            <input value={minAmount} inputMode="decimal" onChange={(event) => setMinAmount(event.target.value)} />
          </label>
          <label className="field">
            <span>monto máx.</span>
            <input value={maxAmount} inputMode="decimal" onChange={(event) => setMaxAmount(event.target.value)} />
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="btn"
              onClick={() => {
                setText("");
                setStatementId("");
                setDirection("");
                setMethod("");
                setCategory("");
                setDateFrom("");
                setDateTo("");
                setMinAmount("");
                setMaxAmount("");
                setPage(1);
              }}
            >
              limpiar
            </button>
            <button className="btn primary" onClick={() => window.open(exportUrl(params), "_blank")}>
              exportar csv
            </button>
          </div>
        </div>
      </div>

      <div className="panel">
        <h2 className="panel-title">
          resultados {data ? `· ${data.total} movimientos` : ""}
        </h2>
        <div className="table-wrap">
          <table className="grid-table">
            <thead>
              <tr>
                <th
                  onClick={() => {
                    setSort("date");
                    setOrder(order === "asc" ? "desc" : "asc");
                  }}
                  style={{ cursor: "pointer" }}
                >
                  fecha {sort === "date" ? (order === "asc" ? "↑" : "↓") : ""}
                </th>
                <th>hora</th>
                <th>descripción</th>
                <th>contraparte</th>
                <th>banco</th>
                <th>método</th>
                <th>categoría</th>
                <th className="num">cargo</th>
                <th className="num">abono</th>
                <th
                  onClick={() => {
                    setSort("amount");
                    setOrder(order === "asc" ? "desc" : "asc");
                  }}
                  style={{ cursor: "pointer" }}
                  className="num"
                >
                  monto {sort === "amount" ? (order === "asc" ? "↑" : "↓") : ""}
                </th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((operation) => (
                <tr key={operation.id} onClick={() => setSelected(operation)} style={{ cursor: "pointer" }}>
                  <td className="mono">{dateLabel(operation.date_iso)}</td>
                  <td className="mono">{timeLabel(operation.occurred_at)}</td>
                  <td className="desc">
                    {operation.description}
                    <small>
                      {operation.reference ? ` · ref ${operation.reference}` : ""}
                      {operation.concept ? ` · ${operation.concept}` : ""}
                    </small>
                  </td>
                  <td>
                    {operation.counterpart ?? ""}
                    {operation.counterpart_account ? (
                      <small className="muted"> ***{operation.counterpart_account}</small>
                    ) : null}
                  </td>
                  <td>{operation.counterpart_bank ?? ""}</td>
                  <td>{methodLabel(operation.method)}</td>
                  <td>{operation.category}</td>
                  <td className="num num-cargo">{operation.cargo ? money(operation.cargo) : ""}</td>
                  <td className="num num-abono">{operation.abono ? money(operation.abono) : ""}</td>
                  <td className="num">{money(operation.amount)}</td>
                </tr>
              ))}
              {data && data.items.length === 0 && (
                <tr>
                  <td colSpan={10} className="muted">
                    Nada coincide con los filtros.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="pager">
          <button className="btn" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            ◀ ant
          </button>
          <span>
            página {data?.page ?? 1} / {totalPages}
          </span>
          <button className="btn" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
            sig ▶
          </button>
        </div>
      </div>

      {selected && (
        <div className="panel">
          <h2 className="panel-title">detalle de la operación</h2>
          <div className="kv" style={{ marginBottom: 12 }}>
            <div>
              <span>fecha</span>
              {selected.date} {selected.occurred_at ? `· ${selected.occurred_at}` : ""}
            </div>
            <div>
              <span>número</span>
              {selected.number ?? "—"}
            </div>
            <div>
              <span>método</span>
              {methodLabel(selected.method)}
            </div>
            <div>
              <span>categoría</span>
              {selected.category}
            </div>
            <div>
              <span>contraparte</span>
              {selected.counterpart ?? "—"} {selected.counterpart_account ? `***${selected.counterpart_account}` : ""}
            </div>
            <div>
              <span>banco contraparte</span>
              {selected.counterpart_bank ?? "—"}
            </div>
            <div>
              <span>referencia</span>
              {selected.reference ?? "—"}
            </div>
            <div>
              <span>concepto</span>
              {selected.concept ?? "—"}
            </div>
            <div>
              <span>monto</span>
              {selected.abono ? `abono ${money(selected.abono)}` : `cargo ${money(selected.cargo)}`}
            </div>
            <div>
              <span>saldo calculado</span>
              {money(selected.balance_computed)}
            </div>
          </div>
          <p className="panel-note">{selected.description}</p>
          <div style={{ marginTop: 10 }}>
            <button className="btn" onClick={() => setSelected(null)}>
              cerrar
            </button>
          </div>
        </div>
      )}
    </>
  );
}
