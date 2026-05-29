"use client";
import { useState, useEffect } from "react";
import { Receipt, AlertTriangle, CheckCircle } from "lucide-react";
import { api, DARFReport, DARFObligation } from "@/lib/api";
import { TaxExplainer } from "@/components/TaxExplainer";
import { brl, pct, monthName } from "@/lib/format";

function ObligationCard({ o }: { o: DARFObligation }) {
  const gain = parseFloat(o.net_gain_brl);
  const tax = parseFloat(o.tax_due_brl);

  return (
    <div className="bg-white border border-amber-200 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-semibold text-lg">{monthName(o.month)} {o.year}</div>
          {o.is_foreign && (
            <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">Exchange estrangeira</span>
          )}
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
        <div className="flex justify-between text-slate-500">
          <span>Limite de isenção</span>
          <span className="font-mono">
            {o.is_foreign ? "R$ 0,00 (estrangeira)" : brl(o.exempt_threshold_brl)}
          </span>
        </div>
        <div className="border-t border-slate-200 pt-2 flex justify-between">
          <span className="text-slate-600">Base de cálculo</span>
          <span className="font-mono font-medium">{brl(o.taxable_gain_brl)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-600">Alíquota</span>
          <span className="font-mono">{pct(o.tax_rate)}</span>
        </div>
        <div className="border-t border-slate-200 pt-2 flex justify-between font-semibold">
          <span>DARF a pagar</span>
          <span className="font-mono text-red-600">{brl(o.tax_due_brl)}</span>
        </div>
      </div>

      <div className="text-xs text-slate-500 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
        <strong>Como pagar:</strong> Acesse o SICALC (sicalc.receita.fazenda.gov.br), selecione o
        código 4600 (Ganhos Líquidos em Operações na Bolsa), informe o período de apuração{" "}
        <strong>{String(o.month).padStart(2, "0")}/{o.year}</strong> e o valor {brl(o.tax_due_brl)}.
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
      <div className="flex items-center justify-between">
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
            <strong>Exchanges brasileiras:</strong> Se você teve ganho líquido mensal acima de{" "}
            <strong>R$&nbsp;35.000</strong>, deve pagar 15% sobre o valor que exceder esse limite.
            Abaixo disso, o ganho é isento.
          </p>
          <p>
            <strong>Exchanges estrangeiras (Binance global, Coinbase, etc.):</strong> Não há isenção.
            Qualquer ganho, mesmo R$&nbsp;1, é tributável à alíquota de 15%.
          </p>
          <p>
            <strong>Custo médio ponderado:</strong> O custo de aquisição é calculado pela média
            ponderada de todas as suas compras de cada ativo. Quando você vende, o ganho é a
            diferença entre o preço de venda e esse custo médio.
          </p>
          <p>
            <strong>Vencimento:</strong> O DARF deve ser pago até o <em>último dia útil do mês
            seguinte</em> ao do ganho. Código DARF: 4600.
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
                  Seus ganhos ficaram abaixo do limite de isenção em todos os meses, ou não houve vendas.
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
                  <span className="text-slate-500 text-sm ml-2">em {report.obligations.length} mês(es)</span>
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
