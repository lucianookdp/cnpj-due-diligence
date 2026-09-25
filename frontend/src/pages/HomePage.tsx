import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { addToWatchlist, ApiRequestError, fetchCompany, fetchGraph, pdfUrl } from "../api/client";
import type { Company, Graph } from "../api/types";
import { CompanyCard } from "../components/CompanyCard";
import { GraphView } from "../components/GraphView";
import { Icon } from "../components/Icon";
import { BatchCheck } from "../components/BatchCheck";
import { Watchlist } from "../components/Watchlist";

interface HomePageProps {
  authenticated: boolean;
}

export function HomePage({ authenticated }: HomePageProps) {
  const { cnpj: cnpjParam } = useParams<{ cnpj?: string }>();
  const navigate = useNavigate();
  const [cnpjInput, setCnpjInput] = useState(cnpjParam ?? "");
  const [expectedActivityInput, setExpectedActivityInput] = useState("");
  const [company, setCompany] = useState<Company | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [watchlistNotice, setWatchlistNotice] = useState<string | null>(null);
  const [watchlistVersion, setWatchlistVersion] = useState(0);
  const [linkCopied, setLinkCopied] = useState(false);

  async function runSearch(cnpj: string, expectedActivity?: string) {
    setLoading(true);
    setError(null);
    setCompany(null);
    setGraph(null);
    setWatchlistNotice(null);

    try {
      // Strips punctuation before it reaches the API: an encoded "/" in the
      // raw "00.000.000/0001-91" input breaks path routing on the backend.
      const normalizedCnpj = cnpj.replace(/\D/g, "");
      const [companyResult, graphResult] = await Promise.all([
        fetchCompany(normalizedCnpj, expectedActivity || undefined),
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

  // Auto-loads the dossier when arriving via a shared /empresa/:cnpj link.
  useEffect(() => {
    if (cnpjParam) {
      setCnpjInput(cnpjParam);
      runSearch(cnpjParam);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    const normalizedCnpj = cnpjInput.replace(/\D/g, "");
    if (!normalizedCnpj) return;
    navigate(`/empresa/${normalizedCnpj}`);
    await runSearch(cnpjInput, expectedActivityInput);
  }

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      setError("Não foi possível copiar o link.");
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

  return (
    <>
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
              {loading ? (
                <>
                  <span className="spinner" />
                  Consultando...
                </>
              ) : (
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
        <div className="feature-grid stagger">
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

      {authenticated && (
        <div className="auth-wrap">
          <Watchlist key={watchlistVersion} onError={setError} />
          <BatchCheck onError={setError} />
        </div>
      )}

      {loading && !company && (
        <div className="card animate-fade-in">
          <div className="skeleton" style={{ height: 26, width: "55%", marginBottom: 14 }} />
          <div className="skeleton" style={{ height: 14, width: "35%", marginBottom: 22 }} />
          <div className="skeleton" style={{ height: 14, width: "100%", marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 14, width: "92%", marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 14, width: "97%", marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 14, width: "80%" }} />
        </div>
      )}

      {company && (
        <>
          <div
            className="field-row animate-fade-in-up"
            style={{ marginBottom: "var(--space-3)" }}
          >
            <a
              href={pdfUrl(company.cnpj, expectedActivityInput || undefined)}
              target="_blank"
              rel="noreferrer"
            >
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
            <button
              type="button"
              className={`btn-with-icon copy-link-btn${linkCopied ? " copied" : ""}`}
              onClick={handleCopyLink}
            >
              <Icon name={linkCopied ? "check" : "link"} size={16} />
              {linkCopied ? "Link copiado!" : "Copiar link"}
            </button>
          </div>
          <CompanyCard company={company} />
        </>
      )}

      {graph && (
        <div className="card animate-fade-in-up">
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
    </>
  );
}
