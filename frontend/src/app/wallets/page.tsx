"use client";
import { useState, useEffect, useRef } from "react";
import { Trash2, Plus, Wallet, Link as LinkIcon, Search, ChevronDown } from "lucide-react";
import { api, Wallet as WalletT, WalletCreate, WalletType, ExchangeInfo } from "@/lib/api";
import { TaxExplainer } from "@/components/TaxExplainer";
import { formatDate } from "@/lib/format";

const ONCHAIN_TYPES: WalletType[] = ["evm_address", "solana_address", "bitcoin_address"];

const ONCHAIN_LABELS: Record<string, string> = {
  evm_address: "Endereço EVM (ETH/BSC/Polygon…)",
  solana_address: "Endereço Solana",
  bitcoin_address: "Endereço Bitcoin",
};

const BLANK: WalletCreate = {
  name: "",
  wallet_type: "ccxt_exchange",
  exchange_id: "",
  api_key: "",
  api_secret: "",
  password: "",
  address: "",
  is_brazilian_exchange: true,
};

// Searchable exchange picker component
function ExchangePicker({
  exchanges,
  value,
  onChange,
}: {
  exchanges: ExchangeInfo[];
  value: string;
  onChange: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const selected = exchanges.find(e => e.id === value);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = exchanges.filter(e =>
    e.id.includes(query.toLowerCase()) || e.name.toLowerCase().includes(query.toLowerCase())
  );
  const popular = filtered.filter(e => e.popular);
  const others = filtered.filter(e => !e.popular);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white hover:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <span className={selected ? "text-slate-900" : "text-slate-600"}>
          {selected ? `${selected.name} (${selected.id})` : "Selecionar exchange…"}
        </span>
        <ChevronDown className="w-4 h-4 text-slate-400 shrink-0" />
      </button>

      {open && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-slate-200 rounded-xl shadow-lg overflow-hidden">
          <div className="p-2 border-b border-slate-100">
            <div className="flex items-center gap-2 px-2 py-1.5 bg-slate-50 rounded-lg">
              <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <input
                autoFocus
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-500"
                placeholder="Buscar exchange…"
                value={query}
                onChange={e => setQuery(e.target.value)}
              />
            </div>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {popular.length > 0 && (
              <>
                <div className="px-3 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider bg-slate-50">
                  Populares
                </div>
                {popular.map(e => (
                  <ExchangeOption key={e.id} exchange={e} selected={e.id === value} onSelect={id => { onChange(id); setOpen(false); setQuery(""); }} />
                ))}
              </>
            )}
            {others.length > 0 && (
              <>
                {popular.length > 0 && (
                  <div className="px-3 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider bg-slate-50">
                    Todas ({others.length})
                  </div>
                )}
                {others.map(e => (
                  <ExchangeOption key={e.id} exchange={e} selected={e.id === value} onSelect={id => { onChange(id); setOpen(false); setQuery(""); }} />
                ))}
              </>
            )}
            {filtered.length === 0 && (
              <div className="px-4 py-6 text-center text-sm text-slate-400">Nenhuma exchange encontrada</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ExchangeOption({ exchange, selected, onSelect }: { exchange: ExchangeInfo; selected: boolean; onSelect: (id: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(exchange.id)}
      className={`w-full text-left px-3 py-2 text-sm flex items-center justify-between hover:bg-blue-50 transition-colors ${selected ? "bg-blue-50 text-blue-700 font-medium" : ""}`}
    >
      <span>{exchange.name}</span>
      <span className="text-xs text-slate-500 font-mono">{exchange.id}</span>
    </button>
  );
}

export default function WalletsPage() {
  const [wallets, setWallets] = useState<WalletT[]>([]);
  const [exchanges, setExchanges] = useState<ExchangeInfo[]>([]);
  const [form, setForm] = useState<WalletCreate>(BLANK);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    const [ws, exs] = await Promise.all([
      api.get<WalletT[]>("/wallets"),
      api.get<ExchangeInfo[]>("/exchanges"),
    ]);
    setWallets(ws);
    setExchanges(exs);
  }

  useEffect(() => { load(); }, []);

  const isExchange = !ONCHAIN_TYPES.includes(form.wallet_type as WalletType);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.post("/wallets", form);
      setForm(BLANK);
      setShowForm(false);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Remover esta carteira e todas as suas transações?")) return;
    await api.delete(`/wallets/${id}`);
    await load();
  }

  function walletLabel(wallet: WalletT): string {
    if (ONCHAIN_TYPES.includes(wallet.wallet_type)) {
      return ONCHAIN_LABELS[wallet.wallet_type] ?? wallet.wallet_type;
    }
    if (wallet.exchange_id) {
      const info = exchanges.find(e => e.id === wallet.exchange_id);
      return info ? `${info.name} (${info.id})` : wallet.exchange_id;
    }
    return wallet.wallet_type;
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Carteiras</h1>
          <p className="text-slate-500 text-sm mt-1">Exchanges e endereços on-chain conectados</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          <Plus className="w-4 h-4" />
          Adicionar carteira
        </button>
      </div>

      <TaxExplainer title="Suas credenciais ficam seguras">
        As chaves de API das exchanges são criptografadas com AES-256 (Fernet) antes de serem
        armazenadas localmente. Elas nunca saem da sua máquina. Para endereços on-chain, apenas
        o endereço público é armazenado.
      </TaxExplainer>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
          <h2 className="font-semibold text-lg">Nova carteira</h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Nome</label>
              <input
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                placeholder="Ex: Binance principal"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Tipo</label>
              <select
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                value={form.wallet_type}
                onChange={e => setForm({ ...form, wallet_type: e.target.value as WalletType, exchange_id: "" })}
              >
                <option value="ccxt_exchange">Exchange (qualquer)</option>
                <optgroup label="On-chain">
                  {ONCHAIN_TYPES.map(t => (
                    <option key={t} value={t}>{ONCHAIN_LABELS[t]}</option>
                  ))}
                </optgroup>
              </select>
            </div>
          </div>

          {isExchange ? (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Exchange</label>
                <ExchangePicker
                  exchanges={exchanges}
                  value={form.exchange_id ?? ""}
                  onChange={id => setForm({ ...form, exchange_id: id })}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
                <input
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono"
                  value={form.api_key}
                  onChange={e => setForm({ ...form, api_key: e.target.value })}
                  placeholder="Chave de API (somente leitura recomendado)"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">API Secret</label>
                <input
                  type="password"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono"
                  value={form.api_secret}
                  onChange={e => setForm({ ...form, api_secret: e.target.value })}
                  placeholder="Secret da API"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Passphrase <span className="text-slate-500 font-normal">(opcional — OKX, Coinbase Pro, etc.)</span>
                </label>
                <input
                  type="password"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono"
                  value={form.password}
                  onChange={e => setForm({ ...form, password: e.target.value })}
                  placeholder="Deixe em branco se não necessário"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_br"
                  checked={form.is_brazilian_exchange}
                  onChange={e => setForm({ ...form, is_brazilian_exchange: e.target.checked })}
                />
                <label htmlFor="is_br" className="text-sm text-slate-700">
                  Exchange brasileira (aplica isenção de R$&nbsp;35.000/mês para DARF)
                </label>
              </div>
            </>
          ) : (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Endereço público</label>
              <input
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono"
                value={form.address}
                onChange={e => setForm({ ...form, address: e.target.value })}
                placeholder="0x… ou endereço Solana/Bitcoin"
                required
              />
            </div>
          )}

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Salvando…" : "Salvar carteira"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 border border-slate-300 rounded-lg text-sm hover:bg-slate-50"
            >
              Cancelar
            </button>
          </div>
        </form>
      )}

      {wallets.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <Wallet className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>Nenhuma carteira adicionada ainda.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {wallets.map(wallet => (
            <div key={wallet.id} className="flex items-center bg-white border border-slate-200 rounded-xl p-4 gap-4">
              <div className="p-2 bg-blue-50 rounded-lg text-blue-600">
                {ONCHAIN_TYPES.includes(wallet.wallet_type) ? <LinkIcon className="w-5 h-5" /> : <Wallet className="w-5 h-5" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium">{wallet.name}</div>
                <div className="text-sm text-slate-500">
                  {walletLabel(wallet)}
                  {wallet.is_brazilian_exchange && !ONCHAIN_TYPES.includes(wallet.wallet_type) && (
                    <span className="ml-2 px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-xs">🇧🇷 BR</span>
                  )}
                </div>
              </div>
              <div className="text-xs text-slate-400 hidden sm:block">{formatDate(wallet.created_at)}</div>
              <button
                onClick={() => handleDelete(wallet.id)}
                className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors shrink-0"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
