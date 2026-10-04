import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Upload } from "../components/Upload";
import { useToast } from "../components/Toast";
import { STATUS_LABEL, moneyShort, progressLabel, statusClass } from "../format";
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
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [processing, load]);

  return (
    <>
      <div className="panel">
        <h2 className="panel-title">subir estados de cuenta</h2>
        <Upload onFinished={() => void load()} />
      </div>

      <div className="panel">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
          <h2 className="panel-title">estados cargados</h2>
          {statements.length > 0 && (
            <button
              className="btn"
              disabled={processing}
              onClick={async () => {
                try {
                  const result = await api.reprocessAll();
                  notify(`Releyendo ${result.queued} estado(s) con el motor actualizado…`);
                  await load();
                } catch (error) {
                  notify(error instanceof Error ? error.message : "No se pudo reprocesar", "error");
                }
              }}
            >
              reprocesar todos
            </button>
          )}
        </div>
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
              {statement.status === "procesando" && (
                <div className="progress-row">
                  <div className="progress">
                    <div className="progress-fill" style={{ width: `${statement.progress_percent}%` }} />
                  </div>
                  <small className="muted">
                    {progressLabel(
                      statement.progress_stage,
                      statement.progress_percent,
                      statement.started_at,
                      statement.queue_position,
                    )}
                  </small>
                </div>
              )}
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
