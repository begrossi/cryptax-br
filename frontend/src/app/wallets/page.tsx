"use client";
import { useState, useEffect } from "react";
import { Trash2, Plus, Wallet, Link as LinkIcon } from "lucide-react";
import { api, Wallet as WalletT, WalletCreate, WalletType } from "@/lib/api";
import { TaxExplainer } from "@/components/TaxExplainer";
import { formatDate } from "@/lib/format";

const EXCHANGE_TYPES: WalletType[] = ["binance", "foxbit", "mercado_bitcoin"];
const ONCHAIN_TYPES: WalletType[] = ["evm_address", "solana_address", "bitcoin_address"];

const TYPE_LABELS: Record<WalletType, string> = {
  binance: "Binance",
  foxbit: "Foxbit",
  mercado_bitcoin: "Mercado Bitcoin",
  evm_address: "Endereço EVM (ETH/BSC/Polygon…)",
  solana_address: "Endereço Solana",
  bitcoin_address: "Endereço Bitcoin",
};

const BLANK: WalletCreate = {
  name: "",
  wallet_type: "binance",
  api_key: "",
  api_secret: "",
  address: "",
  is_brazilian_exchange: true,
};

export default function WalletsPage() {
  const [wallets, setWallets] = useState<WalletT[]>([]);
  const [form, setForm] = useState<WalletCreate>(BLANK);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    const data = await api.get<WalletT[]>("/wallets");
    setWallets(data);
  }

  useEffect(() => { load(); }, []);

  const isExchange = EXCHANGE_TYPES.includes(form.wallet_type);

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
                onChange={e => setForm({ ...form, wallet_type: e.target.value as WalletType })}
              >
                <optgroup label="Exchanges">
                  {EXCHANGE_TYPES.map(t => (
                    <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                  ))}
                </optgroup>
                <optgroup label="On-chain">
                  {ONCHAIN_TYPES.map(t => (
                    <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                  ))}
                </optgroup>
              </select>
            </div>
          </div>

          {isExchange ? (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
                <input
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono"
                  value={form.api_key}
                  onChange={e => setForm({ ...form, api_key: e.target.value })}
                  placeholder="Chave de API da exchange (somente leitura recomendado)"
                  required={isExchange}
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
                  required={isExchange}
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
                required={!isExchange}
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
                  {TYPE_LABELS[wallet.wallet_type]}
                  {wallet.is_brazilian_exchange && (
                    <span className="ml-2 px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-xs">🇧🇷 BR</span>
                  )}
                </div>
              </div>
              <div className="text-xs text-slate-400">{formatDate(wallet.created_at)}</div>
              <button
                onClick={() => handleDelete(wallet.id)}
                className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
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
