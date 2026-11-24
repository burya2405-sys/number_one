import { and, desc, eq, gte, inArray, lte } from "drizzle-orm";
import { getChatGPTUser } from "@/app/chatgpt-auth";
import { getDb } from "@/db";
import { expenses } from "@/db/schema";

const categories = ["Геткурс", "Реклама", "Зарплата", "Прочие"] as const;
type Category = typeof categories[number];
function isCategory(value: unknown): value is Category { return typeof value === "string" && categories.includes(value as Category); }
function errorResponse(error: unknown) { console.error("Expense API error", error); return Response.json({ error: "Не удалось выполнить операцию. Попробуйте ещё раз." }, { status: 500 }); }
function serialize(row: typeof expenses.$inferSelect) { return { id: row.id, date: row.expenseDate, category: row.category, amount: row.amountKopecks / 100, comment: row.comment, source: row.source }; }
async function isAuthorized() { return Boolean(await getChatGPTUser()); }

export async function GET(request: Request) {
  try {
    if (!(await isAuthorized())) return Response.json({ error: "Требуется вход." }, { status: 401 });
    const url = new URL(request.url); const from = url.searchParams.get("from") || "0000-01-01"; const to = url.searchParams.get("to") || "9999-12-31";
    const requested = url.searchParams.getAll("category").filter(isCategory); const conditions = [gte(expenses.expenseDate, from), lte(expenses.expenseDate, to)];
    if (requested.length) conditions.push(inArray(expenses.category, requested));
    const rows = await getDb().select().from(expenses).where(and(...conditions)).orderBy(desc(expenses.expenseDate), desc(expenses.id));
    return Response.json({ expenses: rows.map(serialize) });
  } catch (error) { return errorResponse(error); }
}
export async function POST(request: Request) {
  try {
    if (!(await isAuthorized())) return Response.json({ error: "Требуется вход." }, { status: 401 });
    const payload = await request.json() as { date?: string; category?: unknown; amount?: number; comment?: string };
    if (!/^\d{4}-\d{2}-\d{2}$/.test(payload.date ?? "") || !isCategory(payload.category) || !Number.isFinite(payload.amount) || Number(payload.amount) <= 0 || !payload.comment?.trim()) return Response.json({ error: "Проверьте дату, статью, сумму и комментарий." }, { status: 400 });
    const [row] = await getDb().insert(expenses).values({ expenseDate: payload.date!, category: payload.category, amountKopecks: Math.round(Number(payload.amount) * 100), comment: payload.comment.trim(), source: "CRM" }).returning();
    return Response.json({ expense: serialize(row) }, { status: 201 });
  } catch (error) { return errorResponse(error); }
}
export async function PATCH(request: Request) {
  try {
    if (!(await isAuthorized())) return Response.json({ error: "Требуется вход." }, { status: 401 });
    const payload = await request.json() as { id?: number; date?: string; category?: unknown; amount?: number; comment?: string };
    if (!Number.isInteger(payload.id) || !/^\d{4}-\d{2}-\d{2}$/.test(payload.date ?? "") || !isCategory(payload.category) || !Number.isFinite(payload.amount) || Number(payload.amount) <= 0 || !payload.comment?.trim()) return Response.json({ error: "Некорректные данные расхода." }, { status: 400 });
    const [row] = await getDb().update(expenses).set({ expenseDate: payload.date!, category: payload.category, amountKopecks: Math.round(Number(payload.amount) * 100), comment: payload.comment.trim(), updatedAt: new Date().toISOString() }).where(eq(expenses.id, payload.id!)).returning();
    if (!row) return Response.json({ error: "Расход не найден." }, { status: 404 }); return Response.json({ expense: serialize(row) });
  } catch (error) { return errorResponse(error); }
}
export async function DELETE(request: Request) {
  try { if (!(await isAuthorized())) return Response.json({ error: "Требуется вход." }, { status: 401 }); const id = Number(new URL(request.url).searchParams.get("id")); if (!Number.isInteger(id)) return Response.json({ error: "Некорректный идентификатор." }, { status: 400 }); await getDb().delete(expenses).where(eq(expenses.id, id)); return Response.json({ deleted: true }); }
  catch (error) { return errorResponse(error); }
}
