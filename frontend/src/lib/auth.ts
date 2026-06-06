import { createHmac, timingSafeEqual } from "crypto";
import { cookies } from "next/headers";

export async function getSession() {
  const password = process.env.APP_PASSWORD;
  if (!password) return { user: "admin" };

  const secret = process.env.APP_SECRET ?? "default-secret";
  const cookieStore = await cookies();
  const token = cookieStore.get("cryptax-auth")?.value;
  if (!token) return null;

  const expected = createHmac("sha256", secret).update(password).digest("base64");
  const a = Buffer.from(token);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;

  return { user: "admin" };
}
