import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiRequestError, createBatchCheck, getBatchCheck, listBatchChecks } from "../api/client";
import type { BatchCheck as Batch } from "../api/types";
import {
  batchToCsv,
  extractCnpjs,
  formatCnpj,
  MAX_BATCH_SIZE,
  MAX_FILE_BYTES,
  statusLabel,
} from "../lib/batch";
import { Icon } from "./Icon";

const POLL_MS = 2000;

interface BatchCheckProps {
  onError: (message: string) => void;
}

function scoreClass(score: number | null): string {
  if (score === null) return "";
  if (score >= 60) return "batch-score batch-score-high";
  if (score >= 30) return "batch-score batch-score-mid";
  return "batch-score batch-score-low";
}

export function BatchCheck({ onError }: BatchCheckProps) {
  const [text, setText] = useState("");
  const [batch, setBatch] = useState<Batch | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const found = extractCnpjs(text);
  const toCheck = found.slice(0, MAX_BATCH_SIZE);

  // Resume the latest batch after a reload, so a long run isn't lost.
  useEffect(() => {
    listBatchChecks()
      .then((batches) => setBatch(batches[0] ?? null))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!batch || batch.status !== "processing") return;
    const timer = setTimeout(async () => {
      try {
        setBatch(await getBatchCheck(batch.id));
      } catch (err) {
        onError(err instanceof ApiRequestError ? err.message : "Falha ao atualizar a checagem");
      }
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [batch, onError]);

  function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!/\.(csv|txt)$/i.test(file.name)) {
      onError("Envie um arquivo .csv ou .txt (no Excel: Salvar como > CSV).");
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      onError("Arquivo grande demais: o limite é 1 MB.");
      return;
    }
    // Read here, in the browser; only the CNPJs found are ever sent.
    file.text().then(setText, () => onError("Não foi possível ler o arquivo."));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (toCheck.length === 0) return;
    setSubmitting(true);
    try {
      setBatch(await createBatchCheck(toCheck));
      setText("");
    } catch (err) {
      onError(err instanceof ApiRequestError ? err.message : "Falha ao iniciar a checagem");
    } finally {
      setSubmitting(false);
    }
  }

  function handleDownload() {
    if (!batch) return;
    const blob = new Blob([batchToCsv(batch)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `checagem-em-lote-${batch.created_at.slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const doneCount = batch ? batch.items.filter((i) => i.status !== "pending").length : 0;

  return (
    <div className="card">
      <h2 className="section-title">
        <Icon name="search" size={18} />
        Checagem em lote
      </h2>
      <p className="text-faint text-sm" style={{ marginTop: 0 }}>
        Cole uma lista de CNPJs ou escolha uma planilha em CSV. O arquivo é lido no seu navegador:
        só os CNPJs encontrados são enviados. Até {MAX_BATCH_SIZE} por vez.
      </p>

      <form onSubmit={handleSubmit}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={"11.222.333/0001-81\n33.000.167/0001-01"}
          rows={4}
          maxLength={MAX_FILE_BYTES}
          className="batch-textarea"
        />
        <div className="field-row" style={{ marginTop: "var(--space-2)", alignItems: "center" }}>
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.txt,text/csv,text/plain"
            onChange={handleFile}
            hidden
          />
          <button type="button" className="btn-with-icon" onClick={() => fileInput.current?.click()}>
            <Icon name="download" size={16} />
            Escolher arquivo
          </button>
          <button
            type="submit"
            className="btn-primary btn-with-icon"
            disabled={submitting || toCheck.length === 0 || batch?.status === "processing"}
          >
            <Icon name="search" size={16} />
            {toCheck.length > 0 ? `Verificar ${toCheck.length} CNPJ(s)` : "Verificar"}
          </button>
          {found.length > MAX_BATCH_SIZE && (
            <span className="text-faint text-sm">
              {found.length} encontrados; serão verificados os primeiros {MAX_BATCH_SIZE}.
            </span>
          )}
        </div>
      </form>

      {batch && (
        <div style={{ marginTop: "var(--space-4)" }}>
          <div className="field-row" style={{ alignItems: "center", justifyContent: "space-between" }}>
            <span className="muted text-sm">
              {batch.status === "processing"
                ? `Verificando… ${doneCount} de ${batch.items.length}`
                : batch.status === "interrupted"
                  ? `Interrompida em ${doneCount} de ${batch.items.length}. Envie de novo os que faltaram.`
                  : `Concluída em ${new Date(batch.created_at).toLocaleString("pt-BR")}`}
            </span>
            {batch.status !== "processing" && (
              <button type="button" className="btn-sm btn-with-icon" onClick={handleDownload}>
                <Icon name="download" size={13} />
                Baixar CSV
              </button>
            )}
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>CNPJ</th>
                  <th>Empresa</th>
                  <th>Score</th>
                  <th>Alertas</th>
                </tr>
              </thead>
              <tbody>
                {batch.items.map((item) => (
                  <tr key={item.cnpj}>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <Link to={`/empresa/${item.cnpj}`}>{formatCnpj(item.cnpj)}</Link>
                    </td>
                    <td>
                      {item.razao_social ?? <span className="text-faint">{statusLabel(item.status)}</span>}
                      {item.situacao_cadastral && item.situacao_cadastral !== "ATIVA" && (
                        <div className="text-sm muted">{item.situacao_cadastral}</div>
                      )}
                    </td>
                    <td>
                      {item.score !== null ? <span className={scoreClass(item.score)}>{item.score}</span> : "—"}
                    </td>
                    <td className="text-sm">{item.flags.length > 0 ? item.flags.join(" · ") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
