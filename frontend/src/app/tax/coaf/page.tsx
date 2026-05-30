"use client";
import { useState, useEffect } from "react";
import { Shield, CheckCircle, AlertTriangle, Layers } from "lucide-react";
import { api, COAFAlert } from "@/lib/api";
import { TaxExplainer } from "@/components/TaxExplainer";
import { brl, formatDate } from "@/lib/format";

function AlertRow({ alert }: { alert: COAFAlert }) {
  const isStructuring = alert.alert_type === "structuring";
  return (
    <tr className={isStructuring ? "bg-purple-50 hover:bg-purple-100" : "bg-amber-50 hover:bg-amber-100"}>
      <td className="px-4 py-3 text-slate-500">{formatDate(alert.executed_at)}</td>
      <td className="px-4 py-3">
        {isStructuring ? (
          <span className="flex items-center gap-1 text-xs font-medium text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full w-fit">
            <Layers className="w-3 h-3" />
            Fracionamento
          </span>
        ) : (
          <span className="flex items-center gap-1 text-xs font-medium text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full w-fit">
            <AlertTriangle className="w-3 h-3" />
            Transação única
          </span>
        )}
      </td>
      <td className="px-4 py-3 font-mono font-medium">
        {alert.asset ?? <span className="text-slate-400 italic text-xs">múltiplos ativos</span>}
      </td>
      <td className="px-4 py-3 text-right font-mono">
        {alert.amount != null
          ? parseFloat(String(alert.amount)).toFixed(6)
          : <span className="text-slate-400">—</span>}
      </td>
      <td className="px-4 py-3 text-right font-mono font-medium text-amber-700">
        {brl(String(alert.total_brl))}
      </td>
      <td className="px-4 py-3 text-slate-500">{alert.wallet_name}</td>
      <td className="px-4 py-3 text-xs text-slate-500 max-w-xs">{alert.reason}</td>
    </tr>
  );
}

export default function COAFPage() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [alerts, setAlerts] = useState<COAFAlert[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<COAFAlert[]>(`/tax/coaf?year=${year}`);
      setAlerts(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [year]);

  const singleCount = alerts.filter(a => a.alert_type === "single_transaction").length;
  const structuringCount = alerts.filter(a => a.alert_type === "structuring").length;

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">COAF — Monitoramento AML</h1>
          <p className="text-slate-500 text-sm mt-1">Transações acima do limite e padrões suspeitos</p>
        </div>
        <select
          className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
          value={year}
          onChange={e => setYear(Number(e.target.value))}
        >
          {[currentYear, currentYear - 1, currentYear - 2].map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>

      <TaxExplainer title="O que é o COAF e o que monitoramos" variant="warning">
        <div className="space-y-2">
          <p>
            O COAF (Conselho de Controle de Atividades Financeiras) é o órgão brasileiro de
            prevenção à lavagem de dinheiro. Exchanges regulamentadas devem comunicar ao COAF:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>
              <strong>Transação única acima de R$&nbsp;10.000</strong> — reportada automaticamente
              pela exchange ao COAF.
            </li>
            <li>
              <strong>Fracionamento suspeito</strong> — múltiplas transações abaixo do limite
              no mesmo dia que, somadas, ultrapassam R$&nbsp;10.000. Padrão previsto na
              Resolução COAF nº&nbsp;36/2021.
            </li>
          </ul>
          <p className="text-xs text-amber-700 mt-1">
            Esta tela é informativa. Não há obrigação direta do investidor pessoa física — as
            exchanges é que reportam. Mas estar ciente é importante caso o COAF solicite informações.
          </p>
        </div>
      </TaxExplainer>

      {loading && <div className="text-slate-400 text-center py-12">Carregando…</div>}

      {!loading && alerts.length === 0 ? (
        <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl p-5">
          <CheckCircle className="w-6 h-6 text-green-500 shrink-0" />
          <div>
            <div className="font-semibold text-green-800">Nenhum alerta COAF em {year}</div>
            <div className="text-sm text-green-700 mt-0.5">
              Nenhuma transação única acima de R$&nbsp;10.000 e nenhum padrão de fracionamento detectado.
            </div>
          </div>
        </div>
      ) : !loading && (
        <>
          <div className="flex gap-4">
            {singleCount > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm">
                <span className="font-semibold text-amber-800">{singleCount}</span>
                <span className="text-amber-700"> transação(ões) única(s) acima de R$&nbsp;10.000</span>
              </div>
            )}
            {structuringCount > 0 && (
              <div className="bg-purple-50 border border-purple-200 rounded-xl px-4 py-3 text-sm">
                <span className="font-semibold text-purple-800">{structuringCount}</span>
                <span className="text-purple-700"> padrão(ões) de fracionamento detectado(s)</span>
              </div>
            )}
          </div>

          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">Data</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">Tipo</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">Ativo</th>
                  <th className="text-right px-4 py-3 font-medium text-slate-600">Quantidade</th>
                  <th className="text-right px-4 py-3 font-medium text-slate-600">Total (BRL)</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">Carteira</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">Motivo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {alerts.map((alert, i) => <AlertRow key={i} alert={alert} />)}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
