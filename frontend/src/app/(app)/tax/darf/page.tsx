"use client";
import { useState, useEffect } from "react";
import { Receipt, AlertTriangle, CheckCircle } from "lucide-react";
import { api, DARFReport, DARFObligation } from "@/lib/api";
import { TaxExplainer } from "@/components/TaxExplainer";
import { brl, pct, monthName } from "@/lib/format";

function ObligationCard({ o }: { o: DARFObligation }) {
  const carryApplied = parseFloat(o.carryforward_applied_brl);

  return (
    <div className="bg-white border border-amber-200 rounded-xl p-5 space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <div className="font-semibold text-lg">{monthName(o.month)} {o.year}</div>
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-full font-mono font-medium ${
              o.is_foreign
                ? "bg-purple-100 text-purple-700"
                : "bg-blue-100 text-blue-700"
            }`}>
              Código {o.darf_code}
            </span>
            {o.is_foreign
              ? <span className="text-xs text-slate-500">Exchange estrangeira</span>
              : <span className="text-xs text-slate-500">Exchange brasileira</span>
            }
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-red-600">{brl(o.tax_due_brl)}</div>
          <div className="text-xs text-slate-500">Vence em {o.due_date}</div>
        </div>
      </div>

      <div className="bg-slate-50 rounded-lg p-4 space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-600">Ganho líquido no mês</span>
          <span className="font-mono font-medium">{brl(o.net_gain_brl)}</span>
        </div>
        {carryApplied > 0 && (
          <div className="flex justify-between text-green-700">
            <span>Prejuízo compensado de meses anteriores</span>
            <span className="font-mono">− {brl(o.carryforward_applied_brl)}</span>
          </div>
        )}
        {!o.is_foreign && (
          <div className="flex justify-between text-slate-500">
            <span>Limite de isenção (exchange BR)</span>
            <span className="font-mono">{brl(o.exempt_threshold_brl)}</span>
          </div>
        )}
        <div className="border-t border-slate-200 pt-2 flex justify-between">
          <span className="text-slate-600">Base de cálculo</span>
          <span className="font-mono font-medium">{brl(o.taxable_gain_brl)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-600">Alíquota efetiva</span>
          <span className="font-mono">{pct(o.effective_rate)}</span>
        </div>
        <div className="border-t border-slate-200 pt-2 flex justify-between font-semibold">
          <span>DARF a pagar</span>
          <span className="font-mono text-red-600">{brl(o.tax_due_brl)}</span>
        </div>
      </div>

      <div className="text-xs text-slate-600 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2 space-y-1">
        <div>
          <strong>Como pagar:</strong> Acesse o{" "}
          <strong>SICALC</strong> (sicalc.receita.fazenda.gov.br), selecione o código{" "}
          <strong className="font-mono">{o.darf_code}</strong>{" "}
          ({o.is_foreign
            ? "Ganho de Capital na Alienação de Bens ou Direitos"
            : "Ganhos Líquidos em Operações em Bolsa"
          }), informe o período de apuração{" "}
          <strong>{String(o.month).padStart(2, "0")}/{o.year}</strong> e o valor{" "}
          {brl(o.tax_due_brl)}.
        </div>
      </div>
    </div>
  );
}

export default function DARFPage() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [report, setReport] = useState<DARFReport | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<DARFReport>(`/tax/darf?year=${year}`);
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
          <h1 className="text-2xl font-bold">DARF — Ganhos de Capital</h1>
          <p className="text-slate-500 text-sm mt-1">Imposto mensal sobre ganhos em criptomoedas</p>
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

      <TaxExplainer title="Como funciona o DARF para criptomoedas">
        <div className="space-y-2">
          <p>
            <strong>Exchanges brasileiras — código 4600:</strong> Ganho líquido mensal acima de{" "}
            <strong>R$&nbsp;35.000</strong> é tributado. Alíquota progressiva a partir de 15%.
            Prejuízos de meses anteriores são compensados automaticamente.
          </p>
          <p>
            <strong>Exchanges estrangeiras — código 0507:</strong> Qualquer ganho é tributável,
            sem limite de isenção. Prejuízos também compensam meses futuros,
            mas <em>separadamente</em> dos prejuízos em exchanges brasileiras.
          </p>
          <p>
            <strong>Alíquotas progressivas:</strong> 15% até R$&nbsp;5M · 17,5% até R$&nbsp;10M ·
            20% até R$&nbsp;30M · 22,5% acima. Cada faixa incide apenas sobre a parcela
            dentro dela.
          </p>
          <p>
            <strong>Vencimento:</strong> Último dia útil do mês seguinte ao do ganho.
          </p>
        </div>
      </TaxExplainer>

      {loading && <div className="text-slate-400 text-center py-12">Calculando…</div>}

      {report && !loading && (
        <>
          {report.obligations.length === 0 ? (
            <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl p-5">
              <CheckCircle className="w-6 h-6 text-green-500 shrink-0" />
              <div>
                <div className="font-semibold text-green-800">Nenhum DARF devido em {year}</div>
                <div className="text-sm text-green-700 mt-0.5">
                  Seus ganhos ficaram abaixo do limite de isenção em todos os meses, ou não houve vendas tributáveis.
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
                <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />
                <div>
                  <span className="font-semibold">Total de DARF em {year}: </span>
                  <span className="text-red-600 font-bold text-lg">{brl(report.total_tax_due_brl)}</span>
                  <span className="text-slate-500 text-sm ml-2">em {report.obligations.length} obrigação(ões)</span>
                </div>
              </div>
              <div className="space-y-4">
                {report.obligations.map((o, i) => <ObligationCard key={i} o={o} />)}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
