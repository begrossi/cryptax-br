import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth";
import { Sidebar } from "@/components/Sidebar";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (!session) redirect("/login");

  const authEnabled = !!process.env.APP_PASSWORD;

  return (
    <div className="flex bg-slate-50 text-slate-900 min-h-screen antialiased">
      <Sidebar authEnabled={authEnabled} />
      <main className="flex-1 overflow-auto pt-16 md:pt-0 p-4 md:p-8">{children}</main>
    </div>
  );
}
