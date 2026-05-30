import Link from "next/link";
import { Wallet, Receipt, FileText, Globe, Shield, ArrowRight } from "lucide-react";
import { TaxExplainer } from "@/components/TaxExplainer";

const QUICK_LINKS = [
  {
    href: "/wallets",
    icon: Wallet,
    title: "Adicionar Carteira",
    desc: "Conecte sua exchange ou endereço on-chain",
    color: "bg-blue-100 text-blue-700",
  },
  {
    href: "/tax/darf",
    icon: Receipt,
    title: "Calcular DARF",
    desc: "Veja se há imposto a pagar neste mês",
    color: "bg-amber-100 text-amber-700",
  },
  {
    href: "/tax/irpf",
    icon: FileText,
    title: "Relatório IRPF",
    desc: "Bens e Direitos + rendimentos para declaração",
    color: "bg-green-100 text-green-700",
  },
  {
    href: "/tax/1888",
    icon: Globe,
    title: "IN RFB 1888",
    desc: "Obrigação acessória para exchanges estrangeiras",
    color: "bg-purple-100 text-purple-700",
  },
];

export default function Dashboard() {
  const currentYear = new Date().getFullYear();

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">cryptax-br</h1>
        <p className="text-slate-500 mt-1">
          Declaração de criptoativos para a Receita Federal — open-source, sem enviar dados a terceiros.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {QUICK_LINKS.map(({ href, icon: Icon, title, desc, color }) => (
          <Link
            key={href}
            href={href}
            className="flex items-start gap-4 p-5 bg-white rounded-xl border border-slate-200 hover:border-blue-300 hover:shadow-sm transition-all group"
          >
            <div className={`p-2.5 rounded-lg ${color}`}>
              <Icon className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-slate-900">{title}</div>
              <div className="text-sm text-slate-500 mt-0.5">{desc}</div>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-blue-500 transition-colors mt-1 shrink-0" />
          </Link>
        ))}
      </div>

      <div className="space-y-4">
        <TaxExplainer title="Suas obrigações como investidor em cripto no Brasil">
          <div className="space-y-2">
            <p>
              <strong>IRPF anual</strong> — Declare seus criptoativos em{" "}
              <em>Bens e Direitos</em> (código 89) pelo custo de aquisição em reais. Faça isso
              até o prazo da Receita Federal (geralmente 31 de maio do ano seguinte).
            </p>
            <p>
              <strong>DARF mensal</strong> — Se você vendeu cripto em exchanges brasileiras e teve
              ganho líquido <strong>acima de R$&nbsp;35.000</strong> no mês, deve pagar DARF até
              o último dia útil do mês seguinte. Em exchanges estrangeiras,{" "}
              <strong>qualquer ganho é tributável</strong>, sem limite de isenção.
            </p>
            <p>
              <strong>IN RFB 1888/2019</strong> — Se você operou em exchanges estrangeiras com
              volume mensal acima de R$&nbsp;30.000, deve informar à Receita Federal mensalmente.
            </p>
            <p>
              <strong>COAF</strong> — Transações únicas acima de R$&nbsp;10.000 devem ser
              monitoradas para fins de prevenção à lavagem de dinheiro.
            </p>
          </div>
        </TaxExplainer>

        <TaxExplainer title="Como começar" variant="success">
          <ol className="list-decimal list-inside space-y-1.5">
            <li>
              Vá em <Link href="/wallets" className="font-medium underline">Carteiras</Link> e
              adicione suas exchanges (Binance, Foxbit, etc.) ou endereços on-chain.
            </li>
            <li>
              Em <Link href="/sync" className="font-medium underline">Sincronizar</Link>, importe
              o histórico de transações.
            </li>
            <li>
              Acesse <Link href="/tax/darf" className="font-medium underline">DARF</Link> para ver
              os meses com imposto a pagar em {currentYear}.
            </li>
            <li>
              No final do ano, gere o relatório de{" "}
              <Link href="/tax/irpf" className="font-medium underline">IRPF</Link> para preencher
              sua declaração.
            </li>
          </ol>
        </TaxExplainer>

        <div className="text-xs text-slate-400 pt-2">
          <Shield className="w-3 h-3 inline mr-1" />
          Seus dados ficam armazenados localmente. Nada é enviado a servidores externos além das
          suas próprias exchanges e exploradores de blockchain públicos.
        </div>
      </div>
    </div>
  );
}
