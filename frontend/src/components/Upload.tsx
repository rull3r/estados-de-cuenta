import { useRef, useState } from "react";
import { api } from "../api";
import { useToast } from "./Toast";

export function Upload({ onUploaded }: { onUploaded: (statementId: number) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const notify = useToast();

  async function send(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      notify("Solo se aceptan archivos PDF.", "error");
      return;
    }
    setBusy(true);
    try {
      const statement = await api.upload(file);
      notify(`Recibido: ${file.name}. Procesando y conciliando…`);
      onUploaded(statement.id);
    } catch (error) {
      notify(error instanceof Error ? error.message : "No se pudo subir el archivo", "error");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
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
        const file = event.dataTransfer.files?.[0];
        if (file) void send(file);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
      }}
    >
      <div className="big">{busy ? "procesando…" : "soltar estado de cuenta aquí"}</div>
      <div className="small">
        PDF mensual de Mercantil · Cuenta Corriente · el archivo nunca sale de tu equipo
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void send(file);
        }}
      />
    </div>
  );
}
