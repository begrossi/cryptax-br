import { BookOpen } from "lucide-react";

interface Props {
  title: string;
  children: React.ReactNode;
  variant?: "info" | "warning" | "success";
}

const styles = {
  info: "bg-blue-50 border-blue-200 text-blue-900",
  warning: "bg-amber-50 border-amber-200 text-amber-900",
  success: "bg-green-50 border-green-200 text-green-900",
};

export function TaxExplainer({ title, children, variant = "info" }: Props) {
  return (
    <div className={`rounded-lg border p-4 ${styles[variant]}`}>
      <div className="flex items-center gap-2 font-semibold mb-2">
        <BookOpen className="w-4 h-4" />
        {title}
      </div>
      <div className="text-sm leading-relaxed">{children}</div>
    </div>
  );
}
