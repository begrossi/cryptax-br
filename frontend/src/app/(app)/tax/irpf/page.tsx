"use client";
import { useState, useEffect } from "react";
import { api, IRPFReport, EarnIncomeEntry } from "@/lib/api";
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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
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
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-2 text-xs">
            <div className="bg-white rounded-lg p-3 border border-blue-100">
              <div className="font-semibold text-slate-700 mb-1">📋 Bens e Direitos — Grupo 08, Código 89</div>
              <p>
                Informe cada criptomoeda que você possuía em 31/12/{year}. Valor = <em>custo de aquisição</em> em
                reais (não o valor de mercado). Use o custo médio ponderado calculado abaixo.
              </p>
            </div>
            <div className="bg-white rounded-lg p-3 border border-green-100">
              <div className="font-semibold text-slate-700 mb-1">✅ Rendimentos Isentos e Não Tributáveis — Linha 26 (Outros)</div>
              <p>
                Ganhos em meses com total ≤ R$&nbsp;35.000 em exchanges brasileiras. Discriminação sugerida:{" "}
                <em>&quot;Ganho na alienação de criptoativos — exchanges brasileiras — valor abaixo do limite de isenção (Lei 9.250/95 art. 22).&quot;</em>
              </p>
            </div>
            <div className="bg-white rounded-lg p-3 border border-amber-100">
              <div className="font-semibold text-slate-700 mb-1">💰 Renda Variável → Operações em Bolsa / Mercados</div>
              <p>
                Ganhos tributáveis já pagos via DARF ao longo do ano. Informe os valores mês a mês na aba{" "}
                <em>Renda Variável</em> do programa IRPF. O imposto já pago via DARF é compensado automaticamente.
              </p>
            </div>
            <div className="bg-white rounded-lg p-3 border border-purple-100">
              <div className="font-semibold text-slate-700 mb-1">🌐 Exchanges estrangeiras — Ganho de Capital (código 0507)</div>
              <p>
                Ganhos em exchanges estrangeiras são tratados como <em>ganho de capital na alienação de bens</em>,
                não como renda variável. Declare em <em>Ganhos de Capital</em> no programa GCAP, que gera o
                DARF automaticamente (código 0507).
              </p>
            </div>
          </div>
        </div>
      </TaxExplainer>

      {loading && <div className="text-slate-400 text-center py-12">Calculando…</div>}

      {report && !loading && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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
              <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
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

          {/* Earn income */}
          {report.earn_income.length > 0 && (
            <div>
              <h2 className="font-semibold mb-3">
                Rendimentos recebidos (staking, airdrops) em {year}
              </h2>
              <TaxExplainer title="Atenção: zona cinzenta regulatória" variant="warning">
                A Receita Federal ainda não emitiu orientação definitiva sobre se rendimentos de
                staking e airdrops são tributados <strong>como renda no momento do recebimento</strong>{" "}
                (tabela progressiva, até 27,5%) ou <strong>somente como ganho de capital na venda</strong>{" "}
                (15%). A posição conservadora adotada pela maioria dos contadores é declarar
                como renda tributável no ano do recebimento. Consulte um contador para sua situação.
              </TaxExplainer>
              <div className="mt-3 bg-white border border-slate-200 rounded-xl overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-slate-600">Ativo</th>
                      <th className="text-right px-4 py-3 font-medium text-slate-600">Operações</th>
                      <th className="text-right px-4 py-3 font-medium text-slate-600">Total recebido (BRL)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {report.earn_income.map((e: EarnIncomeEntry) => (
                      <tr key={e.asset} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-mono font-semibold">{e.asset}</td>
                        <td className="px-4 py-3 text-right">{e.transaction_count}</td>
                        <td className="px-4 py-3 text-right font-mono font-medium">{brl(e.total_brl)}</td>
                      </tr>
                    ))}
                    <tr className="bg-slate-50 font-semibold">
                      <td className="px-4 py-3" colSpan={2}>Total</td>
                      <td className="px-4 py-3 text-right font-mono">{brl(report.earn_income_total_brl)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
