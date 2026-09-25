import type { BatchCheck } from "../api/types";

export const MAX_BATCH_SIZE = 50;
// Plenty for a list of a few thousand CNPJs; anything bigger isn't a list.
export const MAX_FILE_BYTES = 1_000_000;

const CNPJ_PATTERN = /\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}/g;

function isValidCnpj(digits: string): boolean {
  if (!/^\d{14}$/.test(digits) || /^(\d)\1+$/.test(digits)) return false;
  const digit = (length: number) => {
    const weights = length === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const sum = weights.reduce((total, weight, i) => total + weight * Number(digits[i]), 0);
    const remainder = sum % 11;
    return remainder < 2 ? 0 : 11 - remainder;
  };
  return digit(12) === Number(digits[12]) && digit(13) === Number(digits[13]);
}

/**
 * Every valid CNPJ in pasted text or a CSV/TXT file, de-duplicated, in the
 * order found. Runs in the browser: the file itself is never uploaded.
 */
export function extractCnpjs(text: string): string[] {
  const found = new Set<string>();
  for (const match of text.matchAll(CNPJ_PATTERN)) {
    const digits = match[0].replace(/\D/g, "");
    if (isValidCnpj(digits)) found.add(digits);
  }
  return [...found];
}

export function formatCnpj(digits: string): string {
  return digits.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
}

const STATUS_LABELS: Record<string, string> = {
  done: "Verificado",
  not_found: "Não encontrado",
  error: "Falhou",
  pending: "Aguardando",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

/** Semicolon-separated so Excel in Portuguese opens it in columns. */
export function batchToCsv(batch: BatchCheck): string {
  // Names come from public registries anyone can edit their way into; a cell
  // starting with = + - @ would run as a spreadsheet formula.
  const cell = (value: string | number | null) => {
    const text = value === null ? "" : String(value);
    const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  const header = ["CNPJ", "Razão social", "Situação", "Score", "Resultado", "Alertas"];
  const rows = batch.items.map((item) => [
    formatCnpj(item.cnpj),
    item.razao_social,
    item.situacao_cadastral,
    item.score,
    statusLabel(item.status),
    item.flags.join(" | "),
  ]);
  return "﻿" + [header, ...rows].map((row) => row.map(cell).join(";")).join("\r\n");
}
