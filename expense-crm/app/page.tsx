"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownToLine, BarChart3, Bot, CalendarDays, ChevronDown, CirclePlus, LayoutDashboard, MoreHorizontal, Pencil, ReceiptText, Search, Trash2, WalletCards } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type Category = "Геткурс" | "Реклама" | "Зарплата" | "Прочие";
type Expense = { id: number; date: string; category: Category; amount: number; comment: string; source: "Telegram" | "CRM" };

const categories: Category[] = ["Геткурс", "Реклама", "Зарплата", "Прочие"];
const categoryStyle: Record<Category, string> = { Геткурс: "tag tag-violet", Реклама: "tag tag-coral", Зарплата: "tag tag-blue", Прочие: "tag tag-amber" };
const money = new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 });
const shortDate = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });

export default function Home() {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [selected, setSelected] = useState<Category[]>(categories);
  const [query, setQuery] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Expense | null>(null);
  const [deleting, setDeleting] = useState<Expense | null>(null);
  const [periodOpen, setPeriodOpen] = useState(false);
  const [dateFrom, setDateFrom] = useState("2026-09-01");
  const [dateTo, setDateTo] = useState("2026-10-07");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const filtered = useMemo(() => expenses.filter((item) => selected.includes(item.category) && item.comment.toLowerCase().includes(query.toLowerCase())), [expenses, selected, query]);
  const total = filtered.reduce((sum, item) => sum + item.amount, 0);
  const currentMonth = filtered.filter((item) => item.date.startsWith("2026-10"));
  const monthTotal = currentMonth.reduce((sum, item) => sum + item.amount, 0);
  const largest = currentMonth.reduce<Expense | null>((max, item) => !max || item.amount > max.amount ? item : max, null);

  function toggleCategory(category: Category) { setSelected((current) => current.includes(category) ? current.filter((item) => item !== category) : [...current, category]); }
  function openCreate() { setEditing(null); setFormOpen(true); }
  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ from: dateFrom, to: dateTo });
    selected.forEach((category) => params.append("category", category));
    setLoading(true);
    fetch(`/api/expenses?${params}`, { signal: controller.signal })
      .then(async (response) => { if (!response.ok) throw new Error(); return response.json() as Promise<{ expenses: Expense[] }>; })
      .then((data) => { setExpenses(data.expenses); setError(""); })
      .catch((reason) => { if (reason?.name !== "AbortError") setError("Не удалось загрузить расходы. Обновите страницу."); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [dateFrom, dateTo, selected]);

  useEffect(() => {
    const modelContext = (document as Document & { modelContext?: { registerTool: (tool: unknown, options?: { signal?: AbortSignal }) => void | Promise<void> } }).modelContext;
    if (!modelContext?.registerTool) return;
    const lifecycle = new AbortController();
    void Promise.resolve(modelContext.registerTool({ name: "list_expenses", title: "Показать расходы", description: "Возвращает расходы, которые сейчас видны с учётом выбранного периода и статей.", inputSchema: { type: "object", properties: {}, additionalProperties: false }, annotations: { readOnlyHint: true, untrustedContentHint: false }, execute: async () => ({ count: filtered.length, total, expenses: filtered }) }, { signal: lifecycle.signal })).catch(() => undefined);
    return () => lifecycle.abort();
  }, [filtered, total]);

  async function saveExpense(formData: FormData) {
    const amount = Number(String(formData.get("amount") ?? "").replace(/\s/g, ""));
    const next = { date: String(formData.get("date")), category: String(formData.get("category")) as Category, amount, comment: String(formData.get("comment")), source: "CRM" as const };
    if (!amount || !next.date || !next.comment) return;
    try {
      const response = await fetch("/api/expenses", { method: editing ? "PATCH" : "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(editing ? { id: editing.id, ...next } : next) });
      const data = await response.json() as { expense?: Expense; error?: string };
      if (!response.ok || !data.expense) throw new Error(data.error);
      setExpenses((current) => editing ? current.map((item) => item.id === editing.id ? data.expense! : item) : [data.expense!, ...current]);
      setFormOpen(false); setEditing(null); setError("");
    } catch (reason) { setError(reason instanceof Error && reason.message ? reason.message : "Не удалось сохранить расход."); }
  }
  function exportCsv() {
    const header = ["Дата", "Статья", "Сумма", "Комментарий", "Источник"];
    const rows = filtered.map((item) => [item.date, item.category, item.amount, item.comment, item.source]);
    const csv = [header, ...rows].map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(";")).join("\n");
    const url = URL.createObjectURL(new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "расходы.csv"; link.click(); URL.revokeObjectURL(url);
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><WalletCards /></span><span>Опора</span></div>
      <nav aria-label="Главная навигация">
        <a className="nav-item active" href="#dashboard"><LayoutDashboard /> Обзор</a>
        <a className="nav-item" href="#expenses"><ReceiptText /> Расходы</a>
        <a className="nav-item" href="#reports"><BarChart3 /> Отчёты</a>
        <a className="nav-item" href="#bot"><Bot /> Telegram-бот</a>
      </nav>
      <div className="profile-card"><span className="avatar">ТХ</span><div><strong>Татьяна</strong><small>Владелец</small></div></div>
    </aside>

    <main className="workspace" id="dashboard">
      <header className="topbar"><div><p className="eyebrow">Финансы бизнеса</p><h1>Расходы</h1></div><Button onClick={openCreate} className="add-button"><CirclePlus /> Добавить расход</Button></header>
      <section className="filter-row" aria-label="Фильтры">
        <button className="period-button" onClick={() => setPeriodOpen(true)}><CalendarDays /> {new Date(`${dateFrom}T12:00:00`).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })} — {new Date(`${dateTo}T12:00:00`).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })} <ChevronDown /></button>
        <div className="category-filter">{categories.map((category) => <label key={category} className={selected.includes(category) ? "category-check checked" : "category-check"}><Checkbox checked={selected.includes(category)} onCheckedChange={() => toggleCategory(category)} />{category}</label>)}</div>
        <Button variant="outline" onClick={exportCsv} className="export-button"><ArrowDownToLine /> Выгрузить</Button>
      </section>
      <section className="metrics" aria-label="Сводка">
        <article className="metric metric-main"><span>Расходы за октябрь</span><strong>{money.format(monthTotal)}</strong><small>{currentMonth.length} операции</small></article>
        <article className="metric"><span>За выбранный период</span><strong>{money.format(total)}</strong><small>{filtered.length} операций</small></article>
        <article className="metric"><span>Самая крупная статья</span><strong>{largest?.category ?? "—"}</strong><small>{largest ? money.format(largest.amount) : "Нет данных"}</small></article>
      </section>
      <section className="content-grid">
        <div className="expense-panel" id="expenses">
          <div className="panel-heading"><div><h2>Все расходы</h2><p>Записи из CRM и Telegram-бота</p></div><div className="search-box"><Search /><Input aria-label="Поиск по комментарию" placeholder="Найти расход" value={query} onChange={(event) => setQuery(event.target.value)} /></div></div>
          {error && <p className="error-banner" role="alert">{error}</p>}
          <div className="expense-list">{loading && <div className="loading-state">Загружаю расходы…</div>}{!loading && filtered.map((item) => <article className="expense-row" key={item.id}>
            <time dateTime={item.date}><strong>{shortDate.format(new Date(`${item.date}T12:00:00`))}</strong><small>2026</small></time>
            <div className="expense-copy"><span className={categoryStyle[item.category]}>{item.category}</span><p>{item.comment}</p><small>{item.source}</small></div>
            <strong className="amount">{money.format(item.amount)}</strong>
            <div className="row-actions"><Button variant="ghost" size="icon-sm" aria-label="Редактировать" onClick={() => { setEditing(item); setFormOpen(true); }}><Pencil /></Button><Button variant="ghost" size="icon-sm" aria-label="Удалить" onClick={() => setDeleting(item)}><Trash2 /></Button></div>
          </article>)}{!loading && filtered.length === 0 && <div className="empty-state"><MoreHorizontal /><h3>Расходов пока нет</h3><p>Добавьте первую запись в CRM или через Telegram-бота.</p></div>}</div>
        </div>
        <aside className="breakdown" id="reports"><div><p className="eyebrow">Структура расходов</p><h2>По статьям</h2></div><div className="donut"><span>{money.format(total)}</span></div><div className="legend">{categories.map((category) => { const sum = filtered.filter((item) => item.category === category).reduce((acc, item) => acc + item.amount, 0); return <div key={category}><span className={`legend-dot ${categoryStyle[category].split(" ")[1]}`} /><span>{category}</span><strong>{money.format(sum)}</strong></div>; })}</div></aside>
      </section>
      <section className="bot-card" id="bot"><span className="bot-icon"><Bot /></span><div><p className="eyebrow">Telegram-бот</p><h2>Быстрое внесение расходов</h2><p>Выберите статью, укажите сумму и добавьте комментарий — расход сразу появится в общем журнале.</p></div><span className="status-pill">Подключён</span></section>
    </main>

    <Dialog open={periodOpen} onOpenChange={setPeriodOpen}><DialogContent className="expense-dialog"><DialogHeader><DialogTitle>Период отчёта</DialogTitle><DialogDescription>Сводка, список и выгрузка будут пересчитаны.</DialogDescription></DialogHeader><form className="expense-form" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); setDateFrom(String(form.get("from"))); setDateTo(String(form.get("to"))); setPeriodOpen(false); }}><label>С даты<Input name="from" type="date" defaultValue={dateFrom} required /></label><label>По дату<Input name="to" type="date" defaultValue={dateTo} required /></label><DialogFooter><Button type="button" variant="outline" onClick={() => setPeriodOpen(false)}>Отмена</Button><Button type="submit">Применить</Button></DialogFooter></form></DialogContent></Dialog>
    <Dialog open={formOpen} onOpenChange={setFormOpen}><DialogContent className="expense-dialog"><DialogHeader><DialogTitle>{editing ? "Изменить расход" : "Новый расход"}</DialogTitle><DialogDescription>Запись сразу появится в общем журнале.</DialogDescription></DialogHeader><form action={saveExpense} className="expense-form">
      <label>Дата<Input name="date" type="date" required defaultValue={editing?.date ?? "2026-10-07"} /></label>
      <label>Статья расходов<Select name="category" defaultValue={editing?.category ?? "Реклама"}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent>{categories.map((category) => <SelectItem key={category} value={category}>{category}</SelectItem>)}</SelectContent></Select></label>
      <label>Сумма, ₽<Input name="amount" type="number" min="1" step="1" required defaultValue={editing?.amount} placeholder="0" /></label>
      <label>Комментарий<Textarea name="comment" required defaultValue={editing?.comment} placeholder="Например, оплата рекламы за октябрь" /></label>
      <DialogFooter><Button type="button" variant="outline" onClick={() => setFormOpen(false)}>Отмена</Button><Button type="submit">{editing ? "Сохранить" : "Добавить"}</Button></DialogFooter>
    </form></DialogContent></Dialog>
    <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Удалить расход?</AlertDialogTitle><AlertDialogDescription>Запись «{deleting?.comment}» будет удалена без возможности восстановления.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction variant="destructive" onClick={async () => { if (!deleting) return; try { const response = await fetch(`/api/expenses?id=${deleting.id}`, { method: "DELETE" }); if (!response.ok) throw new Error(); setExpenses((current) => current.filter((item) => item.id !== deleting.id)); setError(""); } catch { setError("Не удалось удалить расход."); } finally { setDeleting(null); } }}>Удалить</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </div>;
}
