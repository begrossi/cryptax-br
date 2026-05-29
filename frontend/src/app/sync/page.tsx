"use client";
import { useState, useEffect } from "react";
import { RefreshCw, CheckCircle, XCircle, Loader } from "lucide-react";
import { api, Wallet, SyncLog } from "@/lib/api";
import { TaxExplainer } from "@/components/TaxExplainer";
import { formatDate } from "@/lib/format";

function StatusBadge({ status }: { status: SyncLog["status"] }) {
  const map = {
    running: { icon: Loader, cls: "text-blue-600 bg-blue-50", label: "Sincronizando" },
    success: { icon: CheckCircle, cls: "text-green-600 bg-green-50", label: "Concluído" },
    error: { icon: XCircle, cls: "text-red-600 bg-red-50", label: "Erro" },
  };
  const { icon: Icon, cls, label } = map[status];
  return (
    <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      <Icon className="w-3 h-3" />
      {label}
    </span>
  );
}

export default function SyncPage() {
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [logs, setLogs] = useState<SyncLog[]>([]);
  const [syncing, setSyncing] = useState<number | "all" | null>(null);

  async function load() {
    const [ws, ls] = await Promise.all([
      api.get<Wallet[]>("/wallets"),
      api.get<SyncLog[]>("/sync/status"),
    ]);
    setWallets(ws);
    setLogs(ls);
  }

  useEffect(() => { load(); }, []);

  async function syncWallet(id: number) {
    setSyncing(id);
    try {
      await api.post(`/sync/${id}`);
      setTimeout(load, 2000);
    } finally {
      setSyncing(null);
    }
  }

  async function syncAll() {
    setSyncing("all");
    try {
      await api.post("/sync/all");
      setTimeout(load, 2000);
    } finally {
      setSyncing(null);
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Sincronizar</h1>
          <p className="text-slate-500 text-sm mt-1">Importe transações das suas carteiras</p>
        </div>
        <button
          onClick={syncAll}
          disabled={syncing !== null}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${syncing === "all" ? "animate-spin" : ""}`} />
          Sincronizar tudo
        </button>
      </div>

      <TaxExplainer title="Como funciona a sincronização">
        Para exchanges, buscamos seu histórico de negociações, depósitos e saques via API.
        Para endereços on-chain, consultamos exploradores públicos (Etherscan, etc.) para obter
        as transações do endereço. Preços históricos em BRL são buscados via CoinGecko.
        A sincronização é <strong>incremental</strong> — só busca o que ainda não foi importado.
      </TaxExplainer>

      {wallets.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          Adicione carteiras primeiro antes de sincronizar.
        </div>
      ) : (
        <div className="space-y-3">
          {wallets.map(wallet => {
            const lastLog = logs.find(l => l.wallet_id === wallet.id);
            return (
              <div key={wallet.id} className="flex items-center bg-white border border-slate-200 rounded-xl p-4 gap-4">
                <div className="flex-1 min-w-0">
                  <div className="font-medium">{wallet.name}</div>
                  <div className="text-sm text-slate-500">{wallet.wallet_type}</div>
                  {lastLog && (
                    <div className="mt-1 text-xs text-slate-400">
                      Última sync: {formatDate(lastLog.started_at)}
                      {lastLog.status === "success" && ` · ${lastLog.transactions_added} transações adicionadas`}
                      {lastLog.error_message && (
                        <span className="text-red-500 ml-2">{lastLog.error_message}</span>
                      )}
                    </div>
                  )}
                </div>
                {lastLog && <StatusBadge status={lastLog.status} />}
                <button
                  onClick={() => syncWallet(wallet.id)}
                  disabled={syncing !== null}
                  className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 rounded-lg text-sm hover:bg-slate-50 disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${syncing === wallet.id ? "animate-spin" : ""}`} />
                  Sincronizar
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
