"use client";
import { useState, useEffect } from "react";
import { AlertTriangle, CheckCircle } from "lucide-react";
import { api, IN1888Report } from "@/lib/api";
import { TaxExplainer } from "@/components/TaxExplainer";
import { brl, monthName } from "@/lib/format";

export default function IN1888Page() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [report, setReport] = useState<IN1888Report | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<IN1888Report>(`/tax/1888?year=${year}`);
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
          <h1 className="text-2xl font-bold">IN RFB 1888/2019</h1>
          <p className="text-slate-500 text-sm mt-1">Obrigação acessória para exchanges estrangeiras</p>
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

      <TaxExplainer title="O que é a IN RFB 1888/2019?">
        <div className="space-y-2">
          <p>
            A Instrução Normativa 1888/2019 obriga <strong>exchanges brasileiras</strong> a reportar
            todas as transações de seus clientes à Receita Federal mensalmente.
          </p>
          <p>
            <strong>Para você, investidor:</strong> Se você opera em exchanges <em>estrangeiras</em>{" "}
            (Binance global, Coinbase, Kraken, etc.) e o volume mensal de suas operações superar{" "}
            <strong>R$&nbsp;30.000</strong>, você mesmo deve informar à Receita via o sistema
            e-CAC (preenchendo o arquivo de obrigações acessórias).
          </p>
          <p>
            <strong>Prazo:</strong> Até o último dia útil do mês seguinte ao período de apuração.
          </p>
        </div>
      </TaxExplainer>

      {loading && <div className="text-slate-400 text-center py-12">Calculando…</div>}

      {report && !loading && (
        <>
          {report.months_requiring_report.length === 0 ? (
            <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl p-5">
              <CheckCircle className="w-6 h-6 text-green-500 shrink-0" />
              <div>
                <div className="font-semibold text-green-800">Sem obrigação de declarar em {year}</div>
                <div className="text-sm text-green-700 mt-0.5">
                  Volume mensal em exchanges estrangeiras ficou abaixo de R$&nbsp;30.000 em todos os meses.
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
              <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />
              <div>
                <div className="font-semibold">Você deve informar à Receita em {report.months_requiring_report.length} mês(es):</div>
                <div className="text-sm text-amber-800 mt-0.5">
                  {report.months_requiring_report.map(m => monthName(m)).join(", ")}
                </div>
              </div>
            </div>
          )}

          {report.entries.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-slate-600">Mês</th>
                    <th className="text-left px-4 py-3 font-medium text-slate-600">Exchange</th>
                    <th className="text-right px-4 py-3 font-medium text-slate-600">Operações</th>
                    <th className="text-right px-4 py-3 font-medium text-slate-600">Volume (BRL)</th>
                    <th className="text-center px-4 py-3 font-medium text-slate-600">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {report.entries.map((entry, i) => (
                    <tr key={i} className={entry.must_report ? "bg-amber-50" : ""}>
                      <td className="px-4 py-3">{monthName(entry.month)}</td>
                      <td className="px-4 py-3">{entry.wallet_name}</td>
                      <td className="px-4 py-3 text-right">{entry.transaction_count}</td>
                      <td className="px-4 py-3 text-right font-mono">{brl(entry.total_volume_brl)}</td>
                      <td className="px-4 py-3 text-center">
                        {entry.must_report ? (
                          <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs font-medium">
                            Declarar
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs font-medium">
                            Isento
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
