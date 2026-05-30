const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// Wallet
export type WalletType =
  | "binance" | "foxbit" | "mercado_bitcoin"
  | "evm_address" | "solana_address" | "bitcoin_address";

export interface Wallet {
  id: number;
  name: string;
  wallet_type: WalletType;
  is_brazilian_exchange: boolean;
  created_at: string;
}

export interface WalletCreate {
  name: string;
  wallet_type: WalletType;
  api_key?: string;
  api_secret?: string;
  address?: string;
  is_brazilian_exchange?: boolean;
}

// Transactions
export interface Transaction {
  id: number;
  wallet_id: number;
  external_id: string;
  executed_at: string;
  transaction_type: string;
  asset: string;
  amount: string;
  price_brl: string | null;
  total_brl: string | null;
  cost_basis_brl: string | null;
  chain: string | null;
  notes: string | null;
  is_self_transfer: boolean;
}

// Tax
export interface AssetGain {
  asset: string;
  buy_amount: string;
  sell_amount: string;
  avg_cost_brl: string;
  proceeds_brl: string;
  gain_brl: string;
  is_taxable: boolean;
}

export interface GainReport {
  year: number;
  month: number;
  assets: AssetGain[];
  total_gain_brl: string;
  total_loss_brl: string;
  net_gain_brl: string;
  is_taxable: boolean;
  taxable_reason: string | null;
}

export interface DARFObligation {
  year: number;
  month: number;
  darf_code: string;           // "4600" (BR) or "0507" (foreign)
  is_foreign: boolean;
  net_gain_brl: string;
  carryforward_applied_brl: string;
  exempt_threshold_brl: string;
  taxable_gain_brl: string;
  tax_due_brl: string;
  effective_rate: string;
  due_date: string;
}

export interface DARFReport {
  year: number;
  obligations: DARFObligation[];
  total_tax_due_brl: string;
}

export interface IRPFAsset {
  asset: string;
  codigo_bem: string;
  quantity: string;
  avg_cost_brl: string;
  total_cost_brl: string;
  description: string;
}

export interface EarnIncomeEntry {
  asset: string;
  total_brl: string;
  transaction_count: number;
}

export interface IRPFReport {
  year: number;
  assets: IRPFAsset[];
  total_cost_brl: string;
  exempt_gains_brl: string;
  taxable_gains_brl: string;
  earn_income: EarnIncomeEntry[];
  earn_income_total_brl: string;
}

export interface IN1888Entry {
  year: number;
  month: number;
  wallet_name: string;
  transaction_count: number;
  total_volume_brl: string;
  must_report: boolean;
}

export interface IN1888Report {
  year: number;
  entries: IN1888Entry[];
  months_requiring_report: number[];
}

export interface COAFAlert {
  transaction_id: number;
  executed_at: string;
  asset: string;
  amount: string | number;
  total_brl: string | number;
  wallet_name: string;
  reason: string;
}

export interface SyncLog {
  id: number;
  wallet_id: number;
  started_at: string;
  finished_at: string | null;
  status: "running" | "success" | "error";
  transactions_added: number;
  error_message: string | null;
}
