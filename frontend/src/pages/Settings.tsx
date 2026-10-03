import { useEffect, useState } from "react";
import { api } from "../api";
import { useToast } from "../components/Toast";
import type { Bank, Rule } from "../types";

export default function Settings() {
  const [banks, setBanks] = useState<Bank[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [form, setForm] = useState({ pattern: "", category: "", priority: "100" });
  const notify = useToast();

  async function load() {
    try {
      const [nextBanks, nextRules] = await Promise.all([api.banks(), api.rules()]);
      setBanks(nextBanks);
      setRules(nextRules);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Error al cargar ajustes", "error");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <div className="panel">
        <h2 className="panel-title">bancos soportados</h2>
        <div className="table-wrap">
          <table className="grid-table">
            <thead>
              <tr>
                <th>banco</th>
                <th>estado</th>
              </tr>
            </thead>
            <tbody>
              {banks.map((bank) => (
                <tr key={bank.id}>
                  <td>{bank.name}</td>
                  <td>
                    <span className={`badge ${bank.status === "activo" ? "ok" : "review"}`}>{bank.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="panel-note" style={{ marginTop: 10 }}>
          Cada banco implementa su propio adapter sobre el mismo motor de lectura por coordenadas. Los nuevos
          formatos se agregan sin tocar el resto del sistema.
        </p>
      </div>

      <div className="panel">
        <h2 className="panel-title">reglas de categorías</h2>
        <p className="panel-note" style={{ marginBottom: 12 }}>
          Si un movimiento contiene el texto de la regla, se le asigna esa categoría (sin importar espacios ni
          acentos). Las reglas se aplican de menor a mayor prioridad.
        </p>
        <div className="filters">
          <label className="field">
            <span>texto a buscar</span>
            <input
              value={form.pattern}
              placeholder="ej: supermercado"
              onChange={(event) => setForm({ ...form, pattern: event.target.value })}
            />
          </label>
          <label className="field">
            <span>categoría</span>
            <input
              value={form.category}
              placeholder="ej: Alimentación"
              onChange={(event) => setForm({ ...form, category: event.target.value })}
            />
          </label>
          <label className="field">
            <span>prioridad</span>
            <input
              value={form.priority}
              inputMode="numeric"
              onChange={(event) => setForm({ ...form, priority: event.target.value })}
            />
          </label>
          <button
            className="btn primary"
            onClick={async () => {
              if (!form.pattern || !form.category) {
                notify("Indica texto y categoría.", "error");
                return;
              }
              await api.createRule({
                pattern: form.pattern,
                category: form.category,
                priority: Number(form.priority) || 100,
              });
              setForm({ pattern: "", category: "", priority: "100" });
              notify("Regla creada y categorías recalculadas.");
              await load();
            }}
          >
            agregar regla
          </button>
        </div>
        {rules.length > 0 && (
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="grid-table">
              <thead>
                <tr>
                  <th>texto</th>
                  <th>categoría</th>
                  <th className="num">prioridad</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr key={rule.id}>
                    <td>{rule.pattern}</td>
                    <td>{rule.category}</td>
                    <td className="num">{rule.priority}</td>
                    <td>
                      <button
                        className="btn danger"
                        onClick={async () => {
                          await api.deleteRule(rule.id);
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
        <h2 className="panel-title">privacidad</h2>
        <p className="panel-note">
          Todo el procesamiento ocurre en la máquina donde corre esta aplicación: el PDF se lee localmente y los
          datos se guardan en una base SQLite dentro de la carpeta <code>data/</code>. No hay servicios en la
          nube, cuentas ni telemetría. Para respaldar, copia la carpeta <code>data/</code>; si prefieres
          empezar de cero, elimina los estados desde «estados de cuenta».
        </p>
      </div>
    </>
  );
}
