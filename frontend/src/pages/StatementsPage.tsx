import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Upload } from "../components/Upload";
import { useToast } from "../components/Toast";
import { STATUS_LABEL, moneyShort, statusClass } from "../format";
import type { Statement } from "../types";

export default function StatementsPage() {
  const [statements, setStatements] = useState<Statement[]>([]);
  const notify = useToast();

  const load = useCallback(async () => {
    try {
      setStatements(await api.statements());
    } catch (error) {
      notify(error instanceof Error ? error.message : "Error al cargar", "error");
    }
  }, [notify]);

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
        <h2 className="panel-title">estados cargados</h2>
        {statements.length === 0 && <p className="muted">Aún no hay estados de cuenta.</p>}
        {statements.map((statement) => (
          <div className="statement-row" key={statement.id}>
            <div>
              <div className="period">
                {statement.period_start?.slice(3, 5)}/{statement.period_end?.slice(-2) ?? ""}
              </div>
              <span className={`badge ${statusClass(statement.status)}`}>
                {STATUS_LABEL[statement.status] ?? statement.status}
              </span>
            </div>
            <div>
              <Link className="plain" to={`/estados/${statement.id}`}>
                {statement.period_start} → {statement.period_end}
              </Link>
              <div className="file">{statement.file_name}</div>
            </div>
            <div className="mono">
              <div className="num-abono">+{moneyShort(statement.total_abono)}</div>
              <div className="num-cargo">−{moneyShort(statement.total_cargo)}</div>
            </div>
            <div className="mono">
              <div>{statement.transaction_count} movimientos</div>
              <div className="muted">
                anexo {statement.annex_count} · pos {statement.pos_count}
              </div>
            </div>
            <div>
              <Link className="btn" to={`/estados/${statement.id}`}>
                ver peritaje
              </Link>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
