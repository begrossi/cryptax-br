"use client";
import { useState, useEffect } from "react";
import { api, IRPFReport } from "@/lib/api";
import { TaxExplainer } from "@/components/TaxExplainer";
import { brl } from "@/lib/format";

export default function IRPFPage() {
  const currentYear = new Date().getFullYear() - 1; // IRPF is for the previous year
  const [year, setYear] = useState(currentYear);
  const [report, setReport] = useState<IRPFReport | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<IRPFReport>(`/tax/irpf?year=${year}`);
      setReport(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [year]);

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Declaração IRPF</h1>
          <p className="text-slate-500 text-sm mt-1">Dados para preencher sua declaração anual</p>
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

      <TaxExplainer title="Como declarar criptoativos no IRPF">
        <div className="space-y-2">
          <p>
            <strong>Bens e Direitos — Código 89:</strong> Informe cada criptomoeda que você possuía
            em 31/12/{year}. O valor a declarar é o <em>custo de aquisição</em> em reais (não o
            valor de mercado atual). Use o custo médio ponderado calculado abaixo.
          </p>
          <p>
            <strong>Rendimentos Isentos:</strong> Ganhos em meses com total abaixo de R$&nbsp;35.000
            (exchanges brasileiras) são isentos e vão em "Rendimentos Isentos — Ganhos com alienação".
          </p>
          <p>
            <strong>Rendimentos Tributados Exclusivamente na Fonte:</strong> Ganhos tributados via
            DARF ao longo do ano já foram pagos — informe-os em "Renda Variável".
          </p>
        </div>
      </TaxExplainer>

      {loading && <div className="text-slate-400 text-center py-12">Calculando…</div>}

      {report && !loading && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-sm text-slate-500">Custo total dos ativos</div>
              <div className="text-xl font-bold mt-1">{brl(report.total_cost_brl)}</div>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <div className="text-sm text-green-700">Ganhos isentos</div>
              <div className="text-xl font-bold text-green-700 mt-1">{brl(report.exempt_gains_brl)}</div>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="text-sm text-amber-700">Ganhos tributados (DARF)</div>
              <div className="text-xl font-bold text-amber-700 mt-1">{brl(report.taxable_gains_brl)}</div>
            </div>
          </div>

          {/* Assets table */}
          <div>
            <h2 className="font-semibold mb-3">Bens e Direitos em 31/12/{year}</h2>
            {report.assets.length === 0 ? (
              <div className="text-slate-400 py-8 text-center text-sm">
                Nenhum ativo em carteira em {year}.
              </div>
            ) : (
              <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-slate-600">Ativo</th>
                      <th className="text-left px-4 py-3 font-medium text-slate-600">Código</th>
                      <th className="text-right px-4 py-3 font-medium text-slate-600">Quantidade</th>
                      <th className="text-right px-4 py-3 font-medium text-slate-600">Custo médio</th>
                      <th className="text-right px-4 py-3 font-medium text-slate-600">Custo total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {report.assets.map(asset => (
                      <tr key={asset.asset} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-mono font-semibold">{asset.asset}</td>
                        <td className="px-4 py-3 text-slate-500">{asset.codigo_bem}</td>
                        <td className="px-4 py-3 text-right font-mono">{parseFloat(asset.quantity).toFixed(8)}</td>
                        <td className="px-4 py-3 text-right font-mono">{brl(asset.avg_cost_brl)}</td>
                        <td className="px-4 py-3 text-right font-mono font-medium">{brl(asset.total_cost_brl)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <TaxExplainer title="Discriminação sugerida para Bens e Direitos" variant="info">
            Para cada ativo, use a discriminação:{" "}
            <em>
              &quot;[QUANTIDADE] [ATIVO] adquiridos em [EXCHANGE/CARTEIRA]. Custo de aquisição
              calculado pelo método do custo médio ponderado.&quot;
            </em>
          </TaxExplainer>
        </>
      )}
    </div>
  );
}
