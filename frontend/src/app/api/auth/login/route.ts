import { createHmac, timingSafeEqual } from "crypto";
import { NextRequest, NextResponse } from "next/server";

function computeToken(secret: string, password: string): string {
  return createHmac("sha256", secret).update(password).digest("base64");
}

export async function POST(req: NextRequest) {
  const envPassword = process.env.APP_PASSWORD;
  if (!envPassword) {
    return NextResponse.json({ error: "Auth not configured" }, { status: 500 });
  }

  const secret = process.env.APP_SECRET ?? "default-secret";

  let password: string;
  try {
    const body = await req.json();
    password = body.password ?? "";
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }

  const a = Buffer.from(password);
  const b = Buffer.from(envPassword);
  const valid = a.length === b.length && timingSafeEqual(a, b);

  if (!valid) {
    return NextResponse.json({ error: "Senha incorreta" }, { status: 401 });
  }

  const token = computeToken(secret, envPassword);
  const res = NextResponse.json({ ok: true });
  res.cookies.set("cryptax-auth", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 30 * 24 * 60 * 60,
  });
  return res;
}
