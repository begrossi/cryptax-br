"use client";
import { useState, useEffect } from "react";
import { Shield, CheckCircle } from "lucide-react";
import { api, COAFAlert } from "@/lib/api";
import { TaxExplainer } from "@/components/TaxExplainer";
import { brl, formatDate } from "@/lib/format";

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

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">COAF — Monitoramento AML</h1>
          <p className="text-slate-500 text-sm mt-1">Transações acima do limite de comunicação</p>
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

      <TaxExplainer title="O que é o COAF e o que você precisa saber" variant="warning">
        <div className="space-y-2">
          <p>
            O COAF (Conselho de Controle de Atividades Financeiras) é o órgão brasileiro de
            prevenção à lavagem de dinheiro.
          </p>
          <p>
            <strong>Obrigação das exchanges:</strong> Exchanges regulamentadas no Brasil devem
            comunicar ao COAF operações únicas acima de <strong>R$&nbsp;10.000</strong> e
            padrões suspeitos.
          </p>
          <p>
            <strong>Para você:</strong> Esta tela serve como alerta — as transações listadas
            abaixo provavelmente foram comunicadas pelas exchanges ao COAF. Não há obrigação
            direta do investidor pessoa física, mas é importante estar ciente.
          </p>
        </div>
      </TaxExplainer>

      {loading && <div className="text-slate-400 text-center py-12">Carregando…</div>}

      {!loading && alerts.length === 0 ? (
        <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl p-5">
          <CheckCircle className="w-6 h-6 text-green-500 shrink-0" />
          <div>
            <div className="font-semibold text-green-800">Nenhuma transação acima de R$&nbsp;10.000 em {year}</div>
            <div className="text-sm text-green-700 mt-0.5">
              Todas as suas operações ficaram abaixo do limite de comunicação COAF.
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Data</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Ativo</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Quantidade</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Valor (BRL)</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Carteira</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {alerts.map(alert => (
                <tr key={alert.transaction_id} className="bg-amber-50 hover:bg-amber-100">
                  <td className="px-4 py-3 text-slate-500">{formatDate(alert.executed_at)}</td>
                  <td className="px-4 py-3 font-mono font-medium">{alert.asset}</td>
                  <td className="px-4 py-3 text-right font-mono">{parseFloat(String(alert.amount)).toFixed(6)}</td>
                  <td className="px-4 py-3 text-right font-mono font-medium text-amber-700">
                    {brl(String(alert.total_brl))}
                  </td>
                  <td className="px-4 py-3 text-slate-500">{alert.wallet_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
