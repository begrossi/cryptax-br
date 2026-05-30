"use client";
import { useState, useEffect } from "react";
import { api, GainReport } from "@/lib/api";
import { TaxExplainer } from "@/components/TaxExplainer";
import { brl } from "@/lib/format";

const MONTHS = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

export default function GainsPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [report, setReport] = useState<GainReport | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<GainReport>(`/tax/gains?year=${year}&month=${month}`);
      setReport(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [year, month]);

  const netGain = report ? parseFloat(report.net_gain_brl) : 0;

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Ganhos de Capital</h1>
          <p className="text-slate-500 text-sm mt-1">Resultado mensal por ativo com custo médio ponderado</p>
        </div>
        <div className="flex gap-2">
          <select
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
            value={month}
            onChange={e => setMonth(Number(e.target.value))}
          >
            {MONTHS.map((name, i) => <option key={i + 1} value={i + 1}>{name}</option>)}
          </select>
          <select
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
            value={year}
            onChange={e => setYear(Number(e.target.value))}
          >
            {[now.getFullYear(), now.getFullYear() - 1, now.getFullYear() - 2].map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      <TaxExplainer title="Custo Médio Ponderado — como é calculado">
        O custo médio ponderado (método exigido pela Receita Federal) é recalculado a cada compra:
        <br /><br />
        <code className="bg-blue-100 px-1 rounded">Custo médio = (Total investido) ÷ (Quantidade total)</code>
        <br /><br />
        Quando você vende, o ganho é: <code className="bg-blue-100 px-1 rounded">Preço de venda × qty vendida − Custo médio × qty vendida</code>
      </TaxExplainer>

      {loading && <div className="text-slate-400 text-center py-12">Calculando…</div>}

      {report && !loading && (
        <>
          {/* Net result banner */}
          <div className={`rounded-xl p-5 border ${netGain > 0 ? "bg-amber-50 border-amber-200" : "bg-green-50 border-green-200"}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-medium text-slate-600">Resultado líquido — {MONTHS[month - 1]} {year}</div>
                <div className={`text-2xl sm:text-3xl font-bold mt-1 ${netGain > 0 ? "text-amber-700" : "text-green-700"}`}>
                  {brl(report.net_gain_brl)}
                </div>
              </div>
              <div className="text-right text-sm space-y-1">
                <div className="text-green-600">↑ Ganhos: {brl(report.total_gain_brl)}</div>
                <div className="text-red-500">↓ Perdas: {brl(report.total_loss_brl)}</div>
                {report.is_taxable && (
                  <div className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs font-medium inline-block">
                    Tributável
                  </div>
                )}
              </div>
            </div>
            {report.taxable_reason && (
              <div className="mt-3 text-xs text-amber-700 bg-amber-100 rounded-lg px-3 py-2">
                {report.taxable_reason}
              </div>
            )}
          </div>

          {/* Per-asset breakdown */}
          {report.assets.length === 0 ? (
            <div className="text-slate-400 text-center py-8">Nenhuma operação de venda neste período.</div>
          ) : (
            <div className="space-y-3">
              {report.assets.map(asset => {
                const gain = parseFloat(asset.gain_brl);
                return (
                  <div key={asset.asset} className="bg-white border border-slate-200 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-mono font-bold text-lg">{asset.asset}</span>
                      <span className={`text-lg font-bold ${gain > 0 ? "text-amber-600" : "text-green-600"}`}>
                        {gain > 0 ? "+" : ""}{brl(asset.gain_brl)}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                      <div>
                        <div className="text-slate-500">Custo médio de venda</div>
                        <div className="font-mono mt-0.5">{brl(asset.avg_cost_brl)}</div>
                      </div>
                      <div>
                        <div className="text-slate-500">Receita de venda</div>
                        <div className="font-mono mt-0.5">{brl(asset.proceeds_brl)}</div>
                      </div>
                      <div>
                        <div className="text-slate-500">Quantidade vendida</div>
                        <div className="font-mono mt-0.5">{parseFloat(asset.sell_amount).toFixed(6)}</div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
