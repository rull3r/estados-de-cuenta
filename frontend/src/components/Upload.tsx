import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useToast } from "./Toast";

type ItemStatus = "subiendo" | "en cola" | "CUADRA" | "DIFERENCIAS" | "REVISAR" | "duplicado" | "error";

interface UploadItem {
  key: string;
  name: string;
  status: ItemStatus;
  message?: string;
  statementId?: number;
}

const PENDING: ItemStatus[] = ["subiendo", "en cola"];

const LABEL: Record<ItemStatus, string> = {
  subiendo: "subiendo",
  "en cola": "en cola",
  CUADRA: "cuadra al céntimo",
  DIFERENCIAS: "con diferencias",
  REVISAR: "revisar",
  duplicado: "duplicado",
  error: "error",
};

function badgeClass(status: ItemStatus): string {
  if (status === "CUADRA") return "ok";
  if (status === "DIFERENCIAS" || status === "error") return "diff";
  return "review";
}

export function Upload({ onFinished }: { onFinished?: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [items, setItems] = useState<UploadItem[]>([]);
  const notify = useToast();
  const finishedRef = useRef(onFinished);
  finishedRef.current = onFinished;
  const notifiedRef = useRef(false);

  function patch(key: string, changes: Partial<UploadItem>) {
    setItems((prev) => prev.map((item) => (item.key === key ? { ...item, ...changes } : item)));
  }

  async function send(files: File[]) {
    for (const file of files) {
      const key = `${file.name}:${file.size}:${file.lastModified}:${Math.random().toString(36).slice(2)}`;
      setItems((prev) => [...prev, { key, name: file.name, status: "subiendo" }]);
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        patch(key, { status: "error", message: "No es un PDF" });
        continue;
      }
      try {
        const statement = await api.upload(file);
        patch(key, { status: "en cola", statementId: statement.id });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Error al subir";
        patch(key, {
          status: message.toLowerCase().includes("ya fue cargado") ? "duplicado" : "error",
          message,
        });
      }
    }
    if (inputRef.current) inputRef.current.value = "";
  }

  const pendingCount = items.filter((item) => PENDING.includes(item.status)).length;

  // Un solo sondeo para toda la cola: evita decenas de intervalos simultáneos.
  useEffect(() => {
    if (pendingCount === 0) return;
    const timer = window.setInterval(async () => {
      try {
        const statements = await api.statements();
        setItems((prev) =>
          prev.map((item) => {
            if (!item.statementId || !PENDING.includes(item.status)) return item;
            const statement = statements.find((candidate) => candidate.id === item.statementId);
            if (!statement || statement.status === "procesando") return { ...item, status: "en cola" };
            return {
              ...item,
              status: statement.status as ItemStatus,
              message: statement.error ?? undefined,
            };
          }),
        );
      } catch {
        /* se reintenta en el siguiente ciclo */
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [pendingCount]);

  const allDone = items.length > 0 && pendingCount === 0;
  useEffect(() => {
    if (!allDone) {
      notifiedRef.current = false;
      return;
    }
    if (notifiedRef.current) return;
    notifiedRef.current = true;
    const count = (status: ItemStatus) => items.filter((item) => item.status === status).length;
    const parts = [
      `${count("CUADRA")} cuadran al céntimo`,
      `${count("DIFERENCIAS")} con diferencias`,
    ];
    if (count("duplicado")) parts.push(`${count("duplicado")} duplicados`);
    if (count("error")) parts.push(`${count("error")} con error`);
    notify(`Carga terminada: ${parts.join(", ")}.`);
    finishedRef.current?.();
  }, [allDone, items, notify]);

  return (
    <>
      <div
        className={`dropzone ${dragging ? "drag" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const files = Array.from(event.dataTransfer.files ?? []);
          if (files.length) void send(files);
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
        }}
      >
        <div className="big">
          {pendingCount ? `procesando ${pendingCount} archivo(s)…` : "soltar estados de cuenta aquí"}
        </div>
        <div className="small">
          puedes soltar varios PDFs a la vez · se procesan en cola, uno por uno · nada sale de tu equipo
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            if (files.length) void send(files);
          }}
        />
      </div>

      {items.length > 0 && (
        <div className="queue">
          <div className="queue-head">
            <span>
              {items.length} archivo(s) · {pendingCount} en cola
            </span>
            <button className="btn" disabled={pendingCount > 0} onClick={() => setItems([])}>
              limpiar lista
            </button>
          </div>
          {items.map((item) => (
            <div className="queue-item" key={item.key}>
              <span className="queue-name" title={item.name}>
                {item.name}
              </span>
              <span className={`badge ${badgeClass(item.status)}`}>{LABEL[item.status]}</span>
              {item.message && <span className="queue-msg">{item.message}</span>}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
