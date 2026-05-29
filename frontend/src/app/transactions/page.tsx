"use client";
import { useState, useEffect } from "react";
import { api, Transaction } from "@/lib/api";
import { brl, formatDate } from "@/lib/format";

const TYPE_LABELS: Record<string, string> = {
  buy: "Compra",
  sell: "Venda",
  transfer_in: "Depósito",
  transfer_out: "Saque",
  swap_in: "Swap (recebido)",
  swap_out: "Swap (enviado)",
  earn: "Rendimento",
  fee: "Taxa",
};

const TYPE_COLORS: Record<string, string> = {
  buy: "bg-green-100 text-green-700",
  sell: "bg-red-100 text-red-700",
  transfer_in: "bg-blue-100 text-blue-700",
  transfer_out: "bg-slate-100 text-slate-700",
  swap_in: "bg-purple-100 text-purple-700",
  swap_out: "bg-purple-100 text-purple-600",
  earn: "bg-amber-100 text-amber-700",
  fee: "bg-slate-100 text-slate-500",
};

export default function TransactionsPage() {
  const [txs, setTxs] = useState<Transaction[]>([]);
  const [asset, setAsset] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const params = new URLSearchParams();
    if (asset) params.set("asset", asset);
    params.set("limit", "200");
    const data = await api.get<Transaction[]>(`/transactions?${params}`);
    setTxs(data);
    setLoading(false);
  }

  useEffect(() => { load(); }, [asset]);

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Transações</h1>
        <p className="text-slate-500 text-sm mt-1">Histórico completo de todas as suas operações</p>
      </div>

      <div className="flex gap-3">
        <input
          className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
          placeholder="Filtrar por ativo (BTC, ETH…)"
          value={asset}
          onChange={e => setAsset(e.target.value.toUpperCase())}
        />
      </div>

      {loading ? (
        <div className="text-slate-400 py-12 text-center">Carregando…</div>
      ) : txs.length === 0 ? (
        <div className="text-slate-400 py-12 text-center">
          Nenhuma transação encontrada. Sincronize suas carteiras primeiro.
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Data</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Tipo</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Ativo</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Quantidade</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Valor (BRL)</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Preço unit.</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Rede</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {txs.map(tx => (
                <tr key={tx.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 text-slate-500">{formatDate(tx.executed_at)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${TYPE_COLORS[tx.transaction_type] ?? "bg-slate-100 text-slate-700"}`}>
                      {TYPE_LABELS[tx.transaction_type] ?? tx.transaction_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono font-medium">{tx.asset}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    {parseFloat(tx.amount).toFixed(6)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {brl(tx.total_brl)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-slate-500">
                    {brl(tx.price_brl)}
                  </td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{tx.chain ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
