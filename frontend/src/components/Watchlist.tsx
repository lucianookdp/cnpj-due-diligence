import { useEffect, useState } from "react";
import { addToWatchlist, ApiRequestError, getWatchlist, removeFromWatchlist } from "../api/client";
import type { WatchlistEntry } from "../api/types";
import { Icon } from "./Icon";

const ALERT_LABELS: Record<string, string> = {
  situacao_alterada: "Situação cadastral mudou",
  nova_lista_restritiva: "Nova entrada em lista restritiva",
  socio_alterado: "Quadro societário alterado",
};

interface WatchlistProps {
  onError: (message: string) => void;
}

export function Watchlist({ onError }: WatchlistProps) {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [cnpjInput, setCnpjInput] = useState("");
  const [labelInput, setLabelInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function refresh() {
    try {
      setEntries(await getWatchlist());
    } catch (err) {
      onError(err instanceof ApiRequestError ? err.message : "Falha ao carregar a carteira");
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAdd(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      await addToWatchlist(cnpjInput, labelInput || undefined);
      setCnpjInput("");
      setLabelInput("");
      await refresh();
    } catch (err) {
      onError(err instanceof ApiRequestError ? err.message : "Falha ao adicionar à carteira");
    } finally {
      setLoading(false);
    }
  }

  async function handleRemove(id: string) {
    try {
      await removeFromWatchlist(id);
      await refresh();
    } catch (err) {
      onError(err instanceof ApiRequestError ? err.message : "Falha ao remover da carteira");
    }
  }

  return (
    <div className="card">
      <h2 className="section-title">
        <Icon name="bookmark" size={18} />
        Carteira monitorada
      </h2>

      <form onSubmit={handleAdd} className="field-row" style={{ marginBottom: "var(--space-4)" }}>
        <input
          type="text"
          value={cnpjInput}
          onChange={(e) => setCnpjInput(e.target.value)}
          placeholder="CNPJ para monitorar"
        />
        <input
          type="text"
          value={labelInput}
          onChange={(e) => setLabelInput(e.target.value)}
          placeholder="Rótulo (opcional)"
        />
        <button
          type="submit"
          className="btn-primary btn-with-icon"
          disabled={loading || cnpjInput.trim().length === 0}
        >
          <Icon name="plus" size={16} />
          Adicionar
        </button>
      </form>

      {entries.length === 0 && (
        <p className="text-faint text-sm empty-state">
          <Icon name="bookmark" size={22} />
          Nenhum CNPJ na carteira ainda.
        </p>
      )}

      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {entries.map((entry) => (
          <li key={entry.id} className="watchlist-entry">
            <div className="watchlist-entry-header">
              <div>
                <strong>{entry.razao_social ?? entry.cnpj}</strong>{" "}
                {entry.label && <span className="muted">({entry.label})</span>}
                <div className="muted">
                  {entry.cnpj} · {entry.situacao_cadastral ?? "—"}
                </div>
              </div>
              <button
                type="button"
                className="btn-sm btn-with-icon"
                onClick={() => handleRemove(entry.id)}
              >
                <Icon name="trash" size={13} />
                Remover
              </button>
            </div>
            {entry.recent_alerts.length > 0 && (
              <ul className="watchlist-alerts">
                {entry.recent_alerts.map((alert, i) => (
                  <li key={i} className="alert-line">
                    <Icon name="alert-triangle" size={13} />
                    <span>
                      {ALERT_LABELS[alert.alert_type] ?? alert.alert_type}: {alert.message} (
                      {new Date(alert.detected_at).toLocaleString("pt-BR")})
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
