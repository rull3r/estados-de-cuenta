import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { ToastProvider } from "./components/Toast";
import Dashboard from "./pages/Dashboard";
import Movements from "./pages/Movements";
import StatementDetail from "./pages/StatementDetail";
import StatementsPage from "./pages/StatementsPage";
import Settings from "./pages/Settings";

const NAV = [
  { to: "/", label: "panel" },
  { to: "/movimientos", label: "movimientos" },
  { to: "/estados", label: "estados" },
  { to: "/ajustes", label: "ajustes" },
];

const TITLES: Record<string, string> = {
  "/": "Panel general",
  "/movimientos": "Movimientos",
  "/estados": "Estados de cuenta",
  "/ajustes": "Ajustes y bancos",
};

function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const base = "/" + (location.pathname.split("/")[1] ?? "");
  return (
    <div className="shell">
      <aside className="rail">
        <div className="rail-brand">
          estados
          <br />
          de cuenta
          <small>analizador bancario</small>
        </div>
        <nav className="rail-nav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => `rail-link ${isActive ? "active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          datos 100% locales
          <br />
          v0.1 · mercantil corriente
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <h1>{TITLES[base] ?? "estados de cuenta"}</h1>
          <div className="topbar-meta">
            parseo + conciliación al céntimo
            <br />
            sin nube · sin cuenta · sin telemetría
          </div>
        </header>
        <div className="content">{children}</div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/movimientos" element={<Movements />} />
          <Route path="/estados" element={<StatementsPage />} />
          <Route path="/estados/:id" element={<StatementDetail />} />
          <Route path="/ajustes" element={<Settings />} />
        </Routes>
      </Layout>
    </ToastProvider>
  );
}
