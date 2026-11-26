import { sql } from "drizzle-orm";
import { index, integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const expenses = sqliteTable("expenses", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  expenseDate: text("expense_date").notNull(),
  category: text("category", { enum: ["Геткурс", "Реклама", "Зарплата", "Прочие"] }).notNull(),
  amountKopecks: integer("amount_kopecks").notNull(),
  comment: text("comment").notNull().default(""),
  source: text("source", { enum: ["Telegram", "CRM"] }).notNull().default("CRM"),
  createdAt: text("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
  updatedAt: text("updated_at").notNull().default(sql`CURRENT_TIMESTAMP`),
}, (table) => [index("idx_expenses_date_category").on(table.expenseDate, table.category)]);

export const botSessions = sqliteTable("bot_sessions", {
  telegramUserId: text("telegram_user_id").primaryKey(),
  step: text("step", { enum: ["category", "amount", "comment"] }).notNull(),
  category: text("category"),
  amountKopecks: integer("amount_kopecks"),
  updatedAt: text("updated_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});
