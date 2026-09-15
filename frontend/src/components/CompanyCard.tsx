import { useEffect, useState } from "react";
import type { Company, RestrictiveListMatch, RiskScore } from "../api/types";
import { Icon } from "./Icon";

function useCountUp(target: number, durationMs = 700): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    function tick(now: number) {
      const progress = Math.min((now - start) / durationMs, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs]);
  return value;
}

interface CompanyCardProps {
  company: Company;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("pt-BR");
}

const LIST_LABELS: Record<string, string> = {
  ceis: "CEIS",
  cnep: "CNEP",
  cepim: "CEPIM",
  leniencia: "Acordo de Leniência",
  trabalho_escravo: "Trabalho análogo à escravidão",
};

function RestrictiveListAlert({ matches }: { matches: RestrictiveListMatch[] }) {
  if (matches.length === 0) return null;
  return (
    <div className="alert-banner alert-danger">
      {matches.map((m, i) => (
        <div
          className="alert-line"
          key={i}
          style={i < matches.length - 1 ? { marginBottom: 6 } : undefined}
        >
          <Icon name="alert-triangle" size={14} />
          <span>
            <strong>{LIST_LABELS[m.list_type] ?? m.list_type}</strong>
            {m.reason && <> — {m.reason}</>}
            {m.source_org && <> ({m.source_org})</>}
            {m.sanction_start_date && <> · desde {formatDate(m.sanction_start_date)}</>}
          </span>
        </div>
      ))}
    </div>
  );
}

function StatusPill({ situacao }: { situacao: string }) {
  const isActive = situacao.toUpperCase() === "ATIVA";
  return (
    <span className={`status-pill ${isActive ? "status-active" : "status-inactive"}`}>
      <span className="status-dot" />
      {situacao}
    </span>
  );
}

function scoreColorVars(score: number): { bg: string; border: string; text: string } {
  if (score >= 60) {
    return {
      bg: "var(--color-danger-bg)",
      border: "var(--color-danger-border)",
      text: "var(--color-danger-text)",
    };
  }
  if (score >= 30) {
    return {
      bg: "var(--color-warning-bg)",
      border: "var(--color-warning-border)",
      text: "var(--color-warning-text)",
    };
  }
  return {
    bg: "var(--color-success-bg)",
    border: "var(--color-success-border)",
    text: "var(--color-success-text)",
  };
}

function RiskScoreCard({ risk }: { risk: RiskScore }) {
  const colors = scoreColorVars(risk.score);
  const displayedScore = useCountUp(risk.score);
  return (
    <div
      className="card animate-fade-in-up"
      style={{ marginTop: "var(--space-4)", marginBottom: 0 }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-3)",
          marginBottom: "var(--space-3)",
        }}
      >
        <div
          className="score-badge badge-pop"
          style={{ background: colors.bg, borderColor: colors.border, color: colors.text }}
        >
          {displayedScore}
        </div>
        <div>
          <div className="section-title" style={{ marginBottom: 0 }}>
            <Icon name="shield" size={17} />
            Score de risco
          </div>
          <div className="text-xs text-faint">Motor de regras v{risk.rules_version}</div>
        </div>
      </div>
      <ul className="rule-list">
        {risk.results.map((r) => (
          <li key={r.rule_id} className={r.triggered ? "triggered" : "not-triggered"}>
            <Icon name={r.triggered ? "alert-triangle" : "minus"} size={14} />
            <span>
              {r.label} (peso {r.weight}){r.triggered && r.reason && <> — {r.reason}</>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CompanyCard({ company }: CompanyCardProps) {
  return (
    <div className="card animate-fade-in-up">
      <h2 style={{ marginBottom: 0 }}>{company.razao_social}</h2>
      {company.nome_fantasia && <p className="muted">{company.nome_fantasia}</p>}

      <RestrictiveListAlert matches={company.restrictive_list_matches} />

      <h3 className="section-title">
        <Icon name="building" size={15} />
        Dados cadastrais
      </h3>
      <dl className="dl-grid">
        <dt>CNPJ</dt>
        <dd>{company.cnpj}</dd>
        <dt>Situação cadastral</dt>
        <dd>
          <StatusPill situacao={company.situacao_cadastral} /> desde{" "}
          {formatDate(company.situacao_cadastral_data)}
        </dd>
        <dt>
          <Icon name="calendar" size={13} className="dt-icon" />
          Abertura
        </dt>
        <dd>{formatDate(company.data_abertura)}</dd>
        <dt>
          <Icon name="circle-dollar-sign" size={13} className="dt-icon" />
          Capital social
        </dt>
        <dd>{company.capital_social ?? "—"}</dd>
        <dt>Porte</dt>
        <dd>{company.porte ?? "—"}</dd>
        <dt>Natureza jurídica</dt>
        <dd>{company.natureza_juridica_descricao ?? "—"}</dd>
        <dt>CNAE principal</dt>
        <dd>
          {company.cnae_principal_codigo} — {company.cnae_principal_descricao}
        </dd>
        <dt>
          <Icon name="map-pin" size={13} className="dt-icon" />
          Endereço
        </dt>
        <dd>
          {company.logradouro}, {company.numero} {company.complemento} — {company.bairro},{" "}
          {company.municipio}/{company.uf} {company.cep}
        </dd>
      </dl>

      <h3 className="section-title">
        <Icon name="users" size={15} />
        Quadro societário
      </h3>
      <ul className="partner-list stagger">
        {company.partners.map((partner) => (
          <li key={`${partner.nome}-${partner.cpf_masked}`}>
            {partner.nome} — {partner.qualificacao} ({partner.faixa_etaria}, {partner.cpf_masked})
            <RestrictiveListAlert matches={partner.restrictive_list_matches} />
          </li>
        ))}
      </ul>

      <p className="text-xs text-faint" style={{ marginTop: "var(--space-3)", marginBottom: 0 }}>
        Fonte: {company.source_provider} · Coletado em{" "}
        {new Date(company.source_collected_at).toLocaleString("pt-BR")}
      </p>

      <RiskScoreCard risk={company.risk_score} />
    </div>
  );
}
