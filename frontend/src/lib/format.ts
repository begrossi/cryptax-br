export function brl(value: string | number | null | undefined): string {
  if (value == null) return "—";
  const num = typeof value === "string" ? parseFloat(value) : value;
  return num.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function pct(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return (num * 100).toFixed(1) + "%";
}

const MONTH_NAMES = [
  "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

export function monthName(month: number): string {
  return MONTH_NAMES[month] ?? String(month);
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR");
}
