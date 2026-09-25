export interface SecondaryCnae {
  codigo: string;
  descricao: string;
}

export interface RestrictiveListMatch {
  list_type: string;
  name: string;
  reason: string | null;
  source_org: string | null;
  sanction_start_date: string | null;
  sanction_end_date: string | null;
}

export interface Partner {
  nome: string;
  cpf_masked: string | null;
  faixa_etaria: string | null;
  qualificacao: string | null;
  restrictive_list_matches: RestrictiveListMatch[];
}

export interface RuleResult {
  rule_id: string;
  label: string;
  weight: number;
  triggered: boolean;
  reason: string | null;
}

export interface RiskScore {
  score: number;
  rules_version: number;
  results: RuleResult[];
}

export interface Company {
  id: string;
  cnpj: string;
  razao_social: string;
  nome_fantasia: string | null;
  situacao_cadastral: string;
  situacao_cadastral_data: string | null;
  data_abertura: string | null;
  capital_social: string | null;
  natureza_juridica_codigo: string | null;
  natureza_juridica_descricao: string | null;
  porte: string | null;
  cnae_principal_codigo: string | null;
  cnae_principal_descricao: string | null;
  cnaes_secundarios: SecondaryCnae[];
  logradouro: string | null;
  numero: string | null;
  complemento: string | null;
  bairro: string | null;
  municipio: string | null;
  uf: string | null;
  cep: string | null;
  partners: Partner[];
  source_provider: string;
  source_collected_at: string;
  restrictive_list_matches: RestrictiveListMatch[];
  risk_score: RiskScore;
}

export type NodeType = "company" | "person";
export type EdgeType = "partnership" | "company_partnership";

export interface GraphNode {
  id: string;
  node_type: NodeType;
  label: string;
  cnpj: string | null;
  situacao_cadastral: string | null;
  faixa_etaria: string | null;
  shared_address_company_count: number | null;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  edge_type: EdgeType;
  label: string | null;
}

export interface GraphIndicators {
  shared_partner_person_ids: string[];
  shared_address_keys: Record<string, number>;
}

export interface Graph {
  root_cnpj: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  indicators: GraphIndicators;
}

export interface GraphDelta {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ApiError {
  detail: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface WatchlistAlert {
  alert_type: string;
  message: string;
  detected_at: string;
}

export interface WatchlistEntry {
  id: string;
  cnpj: string;
  label: string | null;
  created_at: string;
  razao_social: string | null;
  situacao_cadastral: string | null;
  recent_alerts: WatchlistAlert[];
}

export interface BatchCheckItem {
  cnpj: string;
  status: "pending" | "done" | "not_found" | "error";
  score: number | null;
  razao_social: string | null;
  situacao_cadastral: string | null;
  flags: string[];
}

export interface BatchCheck {
  id: string;
  status: "processing" | "done" | "interrupted";
  created_at: string;
  items: BatchCheckItem[];
}
