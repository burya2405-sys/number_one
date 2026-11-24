import { env } from "cloudflare:workers";
import { eq } from "drizzle-orm";
import { getDb } from "@/db";
import { botSessions, expenses } from "@/db/schema";

type TelegramEnv = Cloudflare.Env & { TELEGRAM_BOT_TOKEN?: string; TELEGRAM_WEBHOOK_SECRET?: string; TELEGRAM_ALLOWED_USER_ID?: string };
type Update = { message?: { chat: { id: number }; from?: { id: number }; text?: string }; callback_query?: { id: string; from: { id: number }; message?: { chat: { id: number } }; data?: string } };
const allowedCategories = ["Геткурс", "Реклама", "Зарплата", "Прочие"];
const menu = { keyboard: [[{ text: "➕ Добавить расход" }]], resize_keyboard: true };
const categoryKeyboard = { inline_keyboard: allowedCategories.map((category) => [{ text: category, callback_data: `category:${category}` }]) };
async function telegram(method: string, body: Record<string, unknown>) { const token = (env as TelegramEnv).TELEGRAM_BOT_TOKEN; if (!token) throw new Error("TELEGRAM_BOT_TOKEN is not configured"); const response = await fetch(`https://api.telegram.org/bot${token}/${method}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }); if (!response.ok) throw new Error(`Telegram API returned ${response.status}`); }
async function send(chatId: number, text: string, replyMarkup?: unknown) { await telegram("sendMessage", { chat_id: chatId, text, reply_markup: replyMarkup }); }

export async function POST(request: Request) {
  const runtime = env as TelegramEnv;
  if (!runtime.TELEGRAM_WEBHOOK_SECRET || request.headers.get("x-telegram-bot-api-secret-token") !== runtime.TELEGRAM_WEBHOOK_SECRET) return new Response("Forbidden", { status: 403 });
  try {
    const update = await request.json() as Update; const userId = update.callback_query?.from.id ?? update.message?.from?.id; const chatId = update.callback_query?.message?.chat.id ?? update.message?.chat.id;
    if (!userId || !chatId || String(userId) !== runtime.TELEGRAM_ALLOWED_USER_ID) return new Response("OK");
    const db = getDb(); const text = update.message?.text?.trim() ?? ""; const callback = update.callback_query?.data ?? "";
    if (update.callback_query) await telegram("answerCallbackQuery", { callback_query_id: update.callback_query.id });
    if (text === "/start") { await send(chatId, "Готово. Нажмите кнопку, чтобы внести новый расход.", menu); return new Response("OK"); }
    if (text === "➕ Добавить расход") { await db.insert(botSessions).values({ telegramUserId: String(userId), step: "category" }).onConflictDoUpdate({ target: botSessions.telegramUserId, set: { step: "category", category: null, amountKopecks: null, updatedAt: new Date().toISOString() } }); await send(chatId, "Выберите статью расходов:", categoryKeyboard); return new Response("OK"); }
    if (callback.startsWith("category:")) { const category = callback.slice(9); if (!allowedCategories.includes(category)) return new Response("OK"); await db.insert(botSessions).values({ telegramUserId: String(userId), step: "amount", category }).onConflictDoUpdate({ target: botSessions.telegramUserId, set: { step: "amount", category, amountKopecks: null, updatedAt: new Date().toISOString() } }); await send(chatId, `Статья: ${category}\nВведите сумму в рублях:`); return new Response("OK"); }
    const [session] = await db.select().from(botSessions).where(eq(botSessions.telegramUserId, String(userId))).limit(1);
    if (!session) { await send(chatId, "Нажмите «Добавить расход», чтобы начать.", menu); return new Response("OK"); }
    if (session.step === "amount") { const amount = Number(text.replace(",", ".").replace(/\s/g, "")); if (!Number.isFinite(amount) || amount <= 0) { await send(chatId, "Не получилось распознать сумму. Введите число, например: 12500"); return new Response("OK"); } await db.update(botSessions).set({ step: "comment", amountKopecks: Math.round(amount * 100), updatedAt: new Date().toISOString() }).where(eq(botSessions.telegramUserId, String(userId))); await send(chatId, "Добавьте комментарий. Если он не нужен, отправьте /skip"); return new Response("OK"); }
    if (session.step === "comment" && session.category && session.amountKopecks) { const comment = text === "/skip" ? "Без комментария" : text; if (!comment) { await send(chatId, "Напишите комментарий или отправьте /skip"); return new Response("OK"); } await db.insert(expenses).values({ expenseDate: new Date().toISOString().slice(0, 10), category: session.category as "Геткурс" | "Реклама" | "Зарплата" | "Прочие", amountKopecks: session.amountKopecks, comment, source: "Telegram" }); await db.delete(botSessions).where(eq(botSessions.telegramUserId, String(userId))); await send(chatId, `Записано ✓\n${session.category} · ${(session.amountKopecks / 100).toLocaleString("ru-RU")} ₽\n${comment}`, menu); }
    return new Response("OK");
  } catch (error) { console.error("Telegram webhook error", error); return new Response("Error", { status: 500 }); }
}
