import { useEffect, useState } from "react";
import "./App.css";
import {
  addToWatchlist,
  ApiRequestError,
  clearToken,
  fetchCompany,
  fetchGraph,
  getToken,
  pdfUrl,
} from "./api/client";
import type { Company, Graph } from "./api/types";
import { AuthForm } from "./components/AuthForm";
import { CompanyCard } from "./components/CompanyCard";
import { GraphView } from "./components/GraphView";
import { Icon } from "./components/Icon";
import { Watchlist } from "./components/Watchlist";

type Theme = "light" | "dark";

function getInitialTheme(): Theme {
  const stored = localStorage.getItem("theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function App() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [cnpjInput, setCnpjInput] = useState("");
  const [expectedActivityInput, setExpectedActivityInput] = useState("");
  const [company, setCompany] = useState<Company | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [watchlistNotice, setWatchlistNotice] = useState<string | null>(null);
  const [authenticated, setAuthenticated] = useState(() => getToken() !== null);
  const [watchlistVersion, setWatchlistVersion] = useState(0);

  async function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setCompany(null);
    setGraph(null);
    setWatchlistNotice(null);

    try {
      // Strips punctuation before it reaches the API: an encoded "/" in the
      // raw "00.000.000/0001-91" input breaks path routing on the backend.
      const normalizedCnpj = cnpjInput.replace(/\D/g, "");
      const [companyResult, graphResult] = await Promise.all([
        fetchCompany(normalizedCnpj, expectedActivityInput || undefined),
        fetchGraph(normalizedCnpj),
      ]);
      setCompany(companyResult);
      setGraph(graphResult);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Falha ao consultar o CNPJ");
    } finally {
      setLoading(false);
    }
  }

  async function handleAddCurrentToWatchlist() {
    if (!company) return;
    try {
      await addToWatchlist(company.cnpj);
      setWatchlistNotice("Adicionado à carteira monitorada.");
      setWatchlistVersion((v) => v + 1);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Falha ao adicionar à carteira");
    }
  }

  function handleLogout() {
    clearToken();
    setAuthenticated(false);
  }

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
    window.dispatchEvent(new Event("themechange"));
  }, [theme]);

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }

  return (
    <div className="app-shell">
      <div className="app-header">
        <div className="app-brand">
          <span className="app-logo">
            <Icon name="radar" size={26} />
          </span>
          <div>
            <h1>Radar CNPJ</h1>
            <p className="app-header-tagline">Due diligence de empresas brasileiras</p>
          </div>
        </div>
        <div className="app-header-actions">
          {authenticated && (
            <button type="button" className="btn-sm btn-with-icon" onClick={handleLogout}>
              <Icon name="log-out" size={15} />
              Sair
            </button>
          )}
          <button
            type="button"
            className="btn-icon theme-toggle"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Ativar modo claro" : "Ativar modo escuro"}
            title={theme === "dark" ? "Ativar modo claro" : "Ativar modo escuro"}
          >
            <Icon name={theme === "dark" ? "sun" : "moon"} size={17} />
          </button>
        </div>
      </div>

      <div className="hero">
        <span className="hero-badge">
          <Icon name="shield" size={13} />
          Fontes 100% públicas e oficiais
        </span>
        <h2 className="hero-title">Due diligence de qualquer empresa brasileira</h2>
        <p className="hero-subtitle">
          Dossiê cadastral, grafo societário, listas restritivas e score de risco explicável,
          a partir de um CNPJ.
        </p>

        <form onSubmit={handleSearch} className="card hero-search-form">
          <div className="field-row" style={{ marginBottom: "var(--space-2)" }}>
            <input
              type="text"
              value={cnpjInput}
              onChange={(e) => setCnpjInput(e.target.value)}
              placeholder="00.000.000/0000-00"
            />
            <button
              type="submit"
              className="btn-primary btn-with-icon"
              disabled={loading || cnpjInput.trim().length === 0}
            >
              {loading ? "Consultando..." : (
                <>
                  <Icon name="search" size={16} />
                  Consultar
                </>
              )}
            </button>
          </div>
          <input
            type="text"
            value={expectedActivityInput}
            onChange={(e) => setExpectedActivityInput(e.target.value)}
            placeholder="Atividade esperada da empresa (opcional, ex: venda de peças automotivas)"
          />
        </form>
      </div>

      {error && <div className="alert-banner alert-danger">{error}</div>}
      {watchlistNotice && <div className="alert-banner alert-success">{watchlistNotice}</div>}

      {!company && (
        <div className="feature-grid">
          <div className="feature-card">
            <span className="feature-icon">
              <Icon name="building" size={20} />
            </span>
            <h3>Dossiê completo</h3>
            <p>Dados cadastrais, quadro societário e histórico direto da Receita Federal.</p>
          </div>
          <div className="feature-card">
            <span className="feature-icon">
              <Icon name="network" size={20} />
            </span>
            <h3>Grafo societário</h3>
            <p>Sócios em comum, endereços compartilhados e cadeias de participação.</p>
          </div>
          <div className="feature-card">
            <span className="feature-icon">
              <Icon name="shield" size={20} />
            </span>
            <h3>Score de risco</h3>
            <p>Pontuação de 0 a 100, sempre explicando qual regra disparou e por quê.</p>
          </div>
          <div className="feature-card">
            <span className="feature-icon">
              <Icon name="bookmark" size={20} />
            </span>
            <h3>Monitoramento</h3>
            <p>Acompanhe CNPJs na carteira e receba alerta quando algo relevante mudar.</p>
          </div>
        </div>
      )}

      <div className="auth-wrap">
        {authenticated ? (
          <Watchlist key={watchlistVersion} onError={setError} />
        ) : (
          <AuthForm onAuthenticated={() => setAuthenticated(true)} />
        )}
      </div>

      {company && (
        <>
          <div className="field-row" style={{ marginBottom: "var(--space-3)" }}>
            <a href={pdfUrl(company.cnpj, expectedActivityInput || undefined)} target="_blank" rel="noreferrer">
              <button type="button" className="btn-with-icon">
                <Icon name="download" size={16} />
                Baixar PDF
              </button>
            </a>
            {authenticated && (
              <button type="button" className="btn-with-icon" onClick={handleAddCurrentToWatchlist}>
                <Icon name="plus" size={16} />
                Adicionar à carteira
              </button>
            )}
          </div>
          <CompanyCard company={company} />
        </>
      )}

      {graph && (
        <div className="card">
          <h2 className="section-title">
            <Icon name="network" size={18} />
            Grafo societário
          </h2>
          <p className="graph-hint">
            Clique em um nó para expandir. Borda laranja = sócio em comum. Borda vermelha
            tracejada = endereço compartilhado por várias empresas.
          </p>
          <GraphView graph={graph} onError={setError} />
        </div>
      )}
    </div>
  );
}

export default App;
