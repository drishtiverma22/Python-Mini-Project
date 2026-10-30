"""
Expense Tracker  -  GUI version (tkinter)
-----------------------------------------
Run:  python expense_gui.py
Needs: pip install numpy matplotlib      (tkinter comes with Python)
Keep this file in the SAME folder as expense_tracker.py (it reuses its classes).

Pages:  Dashboard | Add Expense | Transactions | Charts | Budget
All data is typed in by the user and saved in expenses.csv / budget.txt.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from expense_tracker import ExpenseTracker, Expense, RecurringExpense, CATEGORIES

NAVY, ACCENT, BG, CARD = "#111827", "#4f46e5", "#f3f4f6", "#ffffff"
TEXT, MUTED, BORDER = "#111827", "#6b7280", "#e5e7eb"
GREEN, ORANGE, RED = "#16a34a", "#f59e0b", "#dc2626"
FONT = "Segoe UI"


# ----------------------- pure logic (no widgets, easy to test) -----------------------
def money(x):
    return f"Rs {x:,.2f}"


def build_expense(date_text, category, amount_text, note, recurring, frequency):
    """Validate form input. Returns (expense, None) or (None, error_message)."""
    date_text = date_text.strip() or date.today().isoformat()
    try:
        d = datetime.strptime(date_text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None, "Date must be in YYYY-MM-DD format (example: 2026-10-25)."
    if category not in CATEGORIES:
        return None, "Please choose a category."
    try:
        amount = float(amount_text.replace(",", ""))
    except ValueError:
        return None, "Amount must be a number."
    if not np.isfinite(amount) or amount <= 0:
        return None, "Amount must be greater than 0."
    note = note.strip()
    if recurring:
        return RecurringExpense(d, category, amount, note, frequency or "Monthly"), None
    return Expense(d, category, amount, note), None


def compute_kpis(tracker):
    """Numbers shown on the dashboard cards (calculated with NumPy)."""
    if not tracker.expenses:
        return {"total": 0.0, "month": 0.0, "avg": 0.0, "top": "-", "count": 0}
    amounts, cats, months = tracker.arrays()
    names, totals = tracker.group_sum(cats, amounts)
    this_month = date.today().strftime("%Y-%m")
    return {"total": float(amounts.sum()),
            "month": float(amounts[months == this_month].sum()),
            "avg": float(amounts.mean()),
            "top": str(names[int(np.argmax(totals))]),
            "count": len(amounts)}


def budget_state(spent, budget):
    """Returns (percent_used, 'ok'|'warn'|'over', message)."""
    if budget <= 0:
        return 0.0, "ok", "No budget set. Set a monthly budget on the Budget page."
    pct = spent / budget * 100
    if spent > budget:
        return 100.0, "over", f"Budget exceeded by {money(spent - budget)}!"
    if pct >= 80:
        return pct, "warn", f"{pct:.0f}% used - only {money(budget - spent)} left."
    return pct, "ok", f"{money(budget - spent)} left this month."


def row_values(e, with_type):
    kind = f"Recurring ({e.frequency})" if isinstance(e, RecurringExpense) else "One-time"
    base = (e.date, e.category, money(e.amount))
    return base + ((kind, e.note) if with_type else (e.note,))


# ------------------------------------- GUI -------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("Expense Tracker")
        root.geometry("1120x720")
        root.minsize(980, 640)
        root.configure(bg=BG)
        self.tracker = ExpenseTracker()
        self.row_expense = {}          # tree row id -> Expense object
        self.budget_widgets = []       # (progressbar, label) pairs to keep in sync
        self.current = "Dashboard"
        self.setup_styles()

        self.nav = {}
        self.build_sidebar()
        self.container = tk.Frame(root, bg=BG)
        self.container.pack(side="left", fill="both", expand=True)

        self.pages = {}
        builders = (("Dashboard", self.build_dashboard), ("Add Expense", self.build_add),
                    ("Transactions", self.build_transactions), ("Charts", self.build_charts),
                    ("Budget", self.build_budget))
        for name, builder in builders:
            frame = tk.Frame(self.container, bg=BG)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.pages[name] = frame
            builder(frame)
        self.show("Dashboard")
        self.refresh_all()

    # ---------------- styling and small helpers ----------------
    def setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Treeview", rowheight=28, font=(FONT, 10), background=CARD,
                    fieldbackground=CARD, foreground=TEXT, borderwidth=0)
        s.configure("Treeview.Heading", font=(FONT, 10, "bold"), background=BORDER,
                    foreground=TEXT, relief="flat")
        s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        for name, color in (("ok", GREEN), ("warn", ORANGE), ("over", RED)):
            s.configure(f"{name}.Horizontal.TProgressbar", troughcolor=BORDER,
                        background=color, thickness=18, borderwidth=0)

    def title(self, parent, text, sub=""):
        tk.Label(parent, text=text, font=(FONT, 20, "bold"), bg=BG, fg=TEXT).pack(
            anchor="w", padx=28, pady=(24, 0))
        tk.Label(parent, text=sub, font=(FONT, 10), bg=BG, fg=MUTED).pack(
            anchor="w", padx=28, pady=(0, 14))

    def button(self, parent, text, command, color=ACCENT):
        return tk.Button(parent, text=text, command=command, bg=color, fg="white", bd=0,
                         font=(FONT, 10, "bold"), padx=16, pady=8, cursor="hand2",
                         activebackground=color, activeforeground="white")

    def card(self, parent):
        return tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)

    def make_tree(self, parent, columns, widths, height):
        wrap = tk.Frame(parent, bg=CARD)
        tree = ttk.Treeview(wrap, columns=columns, show="headings", height=height)
        for c, w in zip(columns, widths):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="e" if c == "Amount" else "w")
        bar = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=bar.set)
        tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        return wrap, tree

    def budget_block(self, parent):
        box = self.card(parent)
        tk.Label(box, text="Monthly budget", font=(FONT, 11, "bold"), bg=CARD, fg=TEXT).pack(
            anchor="w", padx=14, pady=(10, 6))
        bar = ttk.Progressbar(box, maximum=100, style="ok.Horizontal.TProgressbar")
        bar.pack(fill="x", padx=14)
        msg = tk.Label(box, text="", font=(FONT, 10), bg=CARD, fg=MUTED, justify="left")
        msg.pack(anchor="w", padx=14, pady=(6, 12))
        self.budget_widgets.append((bar, msg))
        return box

    # ---------------- sidebar and navigation ----------------
    def build_sidebar(self):
        side = tk.Frame(self.root, bg=NAVY, width=210)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="Expense\nTracker", font=(FONT, 18, "bold"), bg=NAVY, fg="white",
                 justify="left").pack(anchor="w", padx=22, pady=(28, 4))
        tk.Label(side, text="Track. Analyse. Save.", font=(FONT, 9), bg=NAVY, fg="#9ca3af").pack(
            anchor="w", padx=22, pady=(0, 26))
        for name in ("Dashboard", "Add Expense", "Transactions", "Charts", "Budget"):
            b = tk.Button(side, text=name, anchor="w", bd=0, relief="flat", bg=NAVY, fg="white",
                          activebackground=ACCENT, activeforeground="white", font=(FONT, 11),
                          padx=22, pady=12, cursor="hand2", command=lambda n=name: self.show(n))
            b.pack(fill="x")
            self.nav[name] = b

    def show(self, name):
        self.current = name
        self.pages[name].tkraise()
        for n, b in self.nav.items():
            b.configure(bg=ACCENT if n == name else NAVY)
        if name == "Charts":
            self.draw_charts()

    # ---------------- page: Dashboard ----------------
    def build_dashboard(self, page):
        self.title(page, "Dashboard", "Your spending at a glance")
        row = tk.Frame(page, bg=BG)
        row.pack(fill="x", padx=22)
        self.kpi_total = self.kpi(row, 0, "Total spent", ACCENT)
        self.kpi_month = self.kpi(row, 1, "This month", GREEN)
        self.kpi_avg = self.kpi(row, 2, "Average expense", ORANGE)
        self.kpi_top = self.kpi(row, 3, "Top category", RED)
        self.budget_block(page).pack(fill="x", padx=28, pady=14)
        tk.Label(page, text="Recent transactions", font=(FONT, 12, "bold"), bg=BG, fg=TEXT).pack(
            anchor="w", padx=28)
        self.empty_hint = tk.Label(page, text="", font=(FONT, 10), bg=BG, fg=MUTED)
        self.empty_hint.pack(anchor="w", padx=28)
        wrap, self.recent_tree = self.make_tree(page, ("Date", "Category", "Amount", "Note"),
                                                (110, 130, 120, 400), 8)
        wrap.pack(fill="both", expand=True, padx=28, pady=(4, 24))

    def kpi(self, parent, col, title, color):
        f = self.card(parent)
        f.grid(row=0, column=col, sticky="nsew", padx=6)
        parent.grid_columnconfigure(col, weight=1)
        tk.Frame(f, bg=color, height=4).pack(fill="x")
        tk.Label(f, text=title, font=(FONT, 10), bg=CARD, fg=MUTED).pack(anchor="w", padx=14, pady=(10, 0))
        value = tk.Label(f, text="-", font=(FONT, 17, "bold"), bg=CARD, fg=TEXT)
        value.pack(anchor="w", padx=14, pady=(0, 12))
        return value

    # ---------------- page: Add Expense ----------------
    def build_add(self, page):
        self.title(page, "Add Expense", "Enter the details and click Add")
        box = self.card(page)
        box.pack(anchor="nw", padx=28, pady=4)
        self.v_date = tk.StringVar(value=date.today().isoformat())
        self.v_cat = tk.StringVar(value=CATEGORIES[0])
        self.v_amt, self.v_note = tk.StringVar(), tk.StringVar()
        self.v_type, self.v_freq = tk.StringVar(value="One-time"), tk.StringVar(value="Monthly")

        def label(r, text):
            tk.Label(box, text=text, font=(FONT, 10), bg=CARD, fg=MUTED).grid(
                row=r, column=0, sticky="w", padx=(22, 12), pady=10)

        label(0, "Date (YYYY-MM-DD)")
        ttk.Entry(box, textvariable=self.v_date, width=34, font=(FONT, 11)).grid(row=0, column=1, padx=(0, 22))
        label(1, "Category")
        ttk.Combobox(box, textvariable=self.v_cat, values=CATEGORIES, state="readonly",
                     width=32, font=(FONT, 11)).grid(row=1, column=1, padx=(0, 22))
        label(2, "Amount (Rs)")
        amt = ttk.Entry(box, textvariable=self.v_amt, width=34, font=(FONT, 11))
        amt.grid(row=2, column=1, padx=(0, 22))
        label(3, "Note (optional)")
        note = ttk.Entry(box, textvariable=self.v_note, width=34, font=(FONT, 11))
        note.grid(row=3, column=1, padx=(0, 22))
        label(4, "Type")
        kind = tk.Frame(box, bg=CARD)
        kind.grid(row=4, column=1, sticky="w")
        for t in ("One-time", "Recurring"):
            tk.Radiobutton(kind, text=t, value=t, variable=self.v_type, bg=CARD, font=(FONT, 10),
                           command=self.toggle_type, activebackground=CARD).pack(side="left", padx=(0, 14))
        label(5, "Repeats")
        self.freq_box = ttk.Combobox(box, textvariable=self.v_freq, values=["Monthly", "Weekly"],
                                     state="disabled", width=32, font=(FONT, 11))
        self.freq_box.grid(row=5, column=1, padx=(0, 22))
        self.button(box, "Add Expense", self.add_expense).grid(row=6, column=0, columnspan=2,
                                                               sticky="ew", padx=22, pady=(14, 8))
        self.add_status = tk.Label(box, text="", font=(FONT, 10), bg=CARD, fg=MUTED)
        self.add_status.grid(row=7, column=0, columnspan=2, pady=(0, 14))
        amt.bind("<Return>", lambda e: self.add_expense())
        note.bind("<Return>", lambda e: self.add_expense())

    def toggle_type(self):
        self.freq_box.configure(state="readonly" if self.v_type.get() == "Recurring" else "disabled")

    def add_expense(self):
        exp, err = build_expense(self.v_date.get(), self.v_cat.get(), self.v_amt.get(), self.v_note.get(),
                                 self.v_type.get() == "Recurring", self.v_freq.get())
        if err:
            self.add_status.configure(text=err, fg=RED)
            return
        self.tracker.add(exp)
        self.v_amt.set("")
        self.v_note.set("")
        self.add_status.configure(text=f"Added: {exp.category} - {money(exp.amount)}", fg=GREEN)
        self.refresh_all()

    # ---------------- page: Transactions ----------------
    def build_transactions(self, page):
        self.title(page, "Transactions", "Search, review and delete your expenses")
        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", padx=28, pady=(0, 8))
        tk.Label(bar, text="Search:", font=(FONT, 10), bg=BG, fg=MUTED).pack(side="left")
        self.v_search = tk.StringVar()
        ttk.Entry(bar, textvariable=self.v_search, width=24, font=(FONT, 11)).pack(side="left", padx=8)
        self.v_search.trace_add("write", lambda *a: self.refresh_table())
        self.count_label = tk.Label(bar, text="", font=(FONT, 10), bg=BG, fg=MUTED)
        self.count_label.pack(side="left", padx=10)
        self.button(bar, "Clear All", self.clear_all, RED).pack(side="right", padx=(8, 0))
        self.button(bar, "Load Sample Data", self.load_sample, "#0891b2").pack(side="right", padx=(8, 0))
        self.button(bar, "Delete Selected", self.delete_selected, "#374151").pack(side="right")
        wrap, self.tree = self.make_tree(page, ("Date", "Category", "Amount", "Type", "Note"),
                                         (110, 130, 120, 150, 330), 18)
        wrap.pack(fill="both", expand=True, padx=28, pady=(0, 24))

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        self.row_expense = {}
        rows = list(reversed(self.tracker.search(self.v_search.get())))     # newest first
        for e in rows:
            self.row_expense[self.tree.insert("", "end", values=row_values(e, True))] = e
        self.count_label.configure(text=f"{len(rows)} transaction(s)")

    def delete_selected(self):
        chosen = [self.row_expense[i] for i in self.tree.selection() if i in self.row_expense]
        if not chosen:
            messagebox.showinfo("Delete", "Click on a row first, then press Delete Selected.")
            return
        if not messagebox.askyesno("Delete", f"Delete {len(chosen)} selected expense(s)?"):
            return
        for e in chosen:
            self.tracker.delete(self.tracker.sorted_expenses().index(e) + 1)
        self.refresh_all()

    def load_sample(self):
        if self.tracker.expenses and not messagebox.askyesno(
                "Sample data", "Sample data will be ADDED to your existing data. Continue?"):
            return
        self.tracker.load_sample()
        self.refresh_all()

    def clear_all(self):
        if self.tracker.expenses and messagebox.askyesno("Clear all", "Delete ALL expenses? This cannot be undone."):
            self.tracker.expenses = []
            self.tracker.save()
            self.refresh_all()

    # ---------------- page: Charts ----------------
    def build_charts(self, page):
        self.title(page, "Charts", "Monthly trend, category share, comparison and cumulative spending")
        self.fig = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=page)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=28, pady=(0, 8))
        self.button(page, "Save as image", self.save_chart).pack(anchor="e", padx=28, pady=(0, 18))

    def draw_charts(self):
        self.tracker.draw_on(self.fig)
        self.canvas.draw_idle()

    def save_chart(self):
        self.fig.savefig("expense_dashboard.png", dpi=130)
        messagebox.showinfo("Saved", "Chart saved as expense_dashboard.png (in the project folder).")

    # ---------------- page: Budget ----------------
    def build_budget(self, page):
        self.title(page, "Monthly Budget", "Set a limit and track it")
        box = self.card(page)
        box.pack(anchor="nw", padx=28, pady=4)
        self.v_budget = tk.StringVar(value=str(self.tracker.budget) if self.tracker.budget > 0 else "")
        tk.Label(box, text="Monthly budget (Rs)", font=(FONT, 10), bg=CARD, fg=MUTED).grid(
            row=0, column=0, padx=(22, 12), pady=18)
        entry = ttk.Entry(box, textvariable=self.v_budget, width=18, font=(FONT, 11))
        entry.grid(row=0, column=1)
        self.button(box, "Save Budget", self.save_budget).grid(row=0, column=2, padx=22)
        entry.bind("<Return>", lambda e: self.save_budget())
        self.budget_status = tk.Label(box, text="", font=(FONT, 10), bg=CARD, fg=MUTED)
        self.budget_status.grid(row=1, column=0, columnspan=3, pady=(0, 12))
        self.budget_block(page).pack(fill="x", padx=28, pady=14)

    def save_budget(self):
        try:
            value = float(self.v_budget.get().replace(",", ""))
        except ValueError:
            value = 0
        if not np.isfinite(value) or value <= 0:
            self.budget_status.configure(text="Enter a budget greater than 0.", fg=RED)
            return
        self.tracker.budget = value
        self.tracker.save()
        self.budget_status.configure(text="Budget saved.", fg=GREEN)
        self.refresh_all()

    # ---------------- refresh everything after any change ----------------
    def refresh_all(self):
        k = compute_kpis(self.tracker)
        self.kpi_total.configure(text=money(k["total"]))
        self.kpi_month.configure(text=money(k["month"]))
        self.kpi_avg.configure(text=money(k["avg"]))
        self.kpi_top.configure(text=k["top"])

        pct, state, msg = budget_state(k["month"], self.tracker.budget)
        color = {"ok": GREEN, "warn": ORANGE, "over": RED}[state]
        if self.tracker.budget > 0:
            msg = f"Spent {money(k['month'])} of {money(self.tracker.budget)} this month.  {msg}"
        for bar, label in self.budget_widgets:
            bar.configure(style=f"{state}.Horizontal.TProgressbar", value=pct)
            label.configure(text=msg, fg=color)

        self.refresh_table()
        self.recent_tree.delete(*self.recent_tree.get_children())
        for e in list(reversed(self.tracker.sorted_expenses()))[:8]:
            self.recent_tree.insert("", "end", values=row_values(e, False))
        self.empty_hint.configure(
            text="" if self.tracker.expenses else "No expenses yet. Add one, or click 'Load Sample Data' in Transactions.")
        if self.current == "Charts":
            self.draw_charts()


def main():
    try:                                   # sharper text on Windows high-DPI screens
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()