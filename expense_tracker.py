"""
Expense Tracker  -  Python Mini Project
---------------------------------------
Concepts used:
  * Classes, inheritance, polymorphism   (Expense -> RecurringExpense)
  * NumPy      (totals, mean, median, std, grouping, cumulative sum)
  * Matplotlib (line plot, pie chart, bar plot, cumulative plot)
  * File handling (data saved in expenses.csv, budget in budget.txt)
  * Command-line interface (menu driven)

Run:  python expense_tracker.py
Needs: pip install numpy matplotlib
"""
import csv
import os
import random
from datetime import date, datetime, timedelta

import numpy as np
import matplotlib.pyplot as plt

DATA_FILE = "expenses.csv"
BUDGET_FILE = "budget.txt"
CATEGORIES = ["Food", "Travel", "Shopping", "Bills", "Entertainment", "Education", "Health", "Other"]


# =====================================================================
#  CLASSES
# =====================================================================
class Expense:
    """A normal (one-time) expense."""
    kind = "One-time"

    def __init__(self, date_str, category, amount, note=""):
        self.date = date_str            # "YYYY-MM-DD"
        self.category = category
        self.amount = float(amount)
        self.note = note

    def monthly_commitment(self):
        """Money that repeats every month because of this expense (none for one-time)."""
        return 0.0

    def describe(self):
        return f"{self.date} | {self.category:<13} | Rs {self.amount:>9,.2f} | {self.note}"

    def to_row(self):
        return [self.kind, self.date, self.category, self.amount, self.note, ""]


class RecurringExpense(Expense):
    """Child class: an expense that repeats (Netflix, gym, mess fee ...)."""
    kind = "Recurring"

    def __init__(self, date_str, category, amount, note="", frequency="Monthly"):
        super().__init__(date_str, category, amount, note)   # reuse parent's __init__
        self.frequency = frequency                           # "Monthly" or "Weekly"

    def monthly_commitment(self):                            # method overriding
        return self.amount if self.frequency == "Monthly" else self.amount * 52 / 12

    def describe(self):                                      # method overriding
        return super().describe() + f"  [{self.frequency}]"

    def to_row(self):
        row = super().to_row()
        row[-1] = self.frequency
        return row


class ExpenseTracker:
    """Manages all expenses: add / delete / search / analyse / plot."""

    def __init__(self):
        self.expenses = []
        self.budget = 0.0
        self.load()

    # ---------------- file handling ----------------
    def load(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, newline="") as f:
                for r in csv.DictReader(f):
                    if r["kind"] == "Recurring":
                        self.expenses.append(RecurringExpense(r["date"], r["category"], r["amount"],
                                                              r["note"], r["frequency"] or "Monthly"))
                    else:
                        self.expenses.append(Expense(r["date"], r["category"], r["amount"], r["note"]))
        if os.path.exists(BUDGET_FILE):
            try:
                self.budget = float(open(BUDGET_FILE).read().strip())
            except ValueError:
                self.budget = 0.0

    def save(self):
        with open(DATA_FILE, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["kind", "date", "category", "amount", "note", "frequency"])
            for e in self.expenses:
                w.writerow(e.to_row())
        with open(BUDGET_FILE, "w") as f:
            f.write(str(self.budget))

    # ---------------- basic operations ----------------
    def add(self, expense):
        self.expenses.append(expense)
        self.save()

    def sorted_expenses(self):
        return sorted(self.expenses, key=lambda e: e.date)

    def delete(self, number):
        """Delete by the number shown in 'View all' (1-based)."""
        items = self.sorted_expenses()
        if 1 <= number <= len(items):
            self.expenses.remove(items[number - 1])
            self.save()
            return items[number - 1]
        return None

    def search(self, text):
        t = text.strip().lower()
        return [e for e in self.sorted_expenses()
                if t in e.category.lower() or t in e.note.lower() or e.date.startswith(t)]

    # ---------------- NumPy analysis ----------------
    def arrays(self):
        amounts = np.array([e.amount for e in self.expenses])
        cats = np.array([e.category for e in self.expenses])
        months = np.array([e.date[:7] for e in self.expenses])
        return amounts, cats, months

    @staticmethod
    def group_sum(labels, amounts):
        """Total amount per label, e.g. per category or per month."""
        names, inverse = np.unique(labels, return_inverse=True)
        return names, np.bincount(inverse, weights=amounts)

    def summary(self):
        if not self.expenses:
            print("No expenses yet. Add some first (or load sample data).")
            return
        amounts, cats, months = self.arrays()
        hi, lo = int(np.argmax(amounts)), int(np.argmin(amounts))
        print("\n========== SUMMARY ==========")
        print(f"Total expenses   : {len(amounts)}")
        print(f"Total spent      : Rs {np.sum(amounts):,.2f}")
        print(f"Average expense  : Rs {np.mean(amounts):,.2f}")
        print(f"Median expense   : Rs {np.median(amounts):,.2f}")
        print(f"Std deviation    : Rs {np.std(amounts):,.2f}")
        print(f"Highest expense  : {self.expenses[hi].describe()}")
        print(f"Lowest expense   : {self.expenses[lo].describe()}")

        names, totals = self.group_sum(cats, amounts)
        print("\nBy category (highest first):")
        for i in np.argsort(totals)[::-1]:
            print(f"  {names[i]:<14} Rs {totals[i]:>10,.2f}   {totals[i] / totals.sum() * 100:5.1f}%")

        m_names, m_totals = self.group_sum(months, amounts)
        print("\nBy month:")
        for m, t in zip(m_names, m_totals):
            print(f"  {m}   Rs {t:>10,.2f}")

        commit = sum(e.monthly_commitment() for e in self.expenses)
        print(f"\nRecurring commitments per month: Rs {commit:,.2f}")

    def check_budget(self):
        if self.budget <= 0:
            print("No budget set. Use option 7 to set a monthly budget.")
            return
        amounts, _, months = self.arrays() if self.expenses else (np.array([]), None, np.array([]))
        this_month = date.today().strftime("%Y-%m")
        spent = float(amounts[months == this_month].sum()) if len(amounts) else 0.0
        pct = spent / self.budget * 100
        print(f"\nBudget for {this_month}: Rs {self.budget:,.2f} | Spent: Rs {spent:,.2f} ({pct:.1f}%)")
        if spent > self.budget:
            print(f"!! Budget EXCEEDED by Rs {spent - self.budget:,.2f}")
        elif pct >= 80:
            print(f"Warning: you have used {pct:.0f}% of your budget. Only Rs {self.budget - spent:,.2f} left.")
        else:
            print(f"Good going! Rs {self.budget - spent:,.2f} left this month.")

    # ---------------- Matplotlib charts ----------------
    def draw_on(self, fig):
        """Draw the 4-chart dashboard on a Matplotlib Figure (used by both the CLI and the GUI)."""
        fig.clear()
        if not self.expenses:
            fig.text(0.5, 0.5, "No data yet - add some expenses first",
                     ha="center", va="center", fontsize=14, color="gray")
            return
        amounts, cats, months = self.arrays()
        c_names, c_tot = self.group_sum(cats, amounts)
        m_names, m_tot = self.group_sum(months, amounts)

        ax = fig.subplots(2, 2)
        fig.suptitle("Expense Tracker Dashboard", fontsize=16, weight="bold")

        # 1) line plot: monthly trend
        ax[0, 0].plot(m_names, m_tot, marker="o", color="tab:blue")
        if self.budget > 0:
            ax[0, 0].axhline(self.budget, color="red", linestyle="--", label="Budget")
            ax[0, 0].legend()
        ax[0, 0].set_title("Monthly spending")
        ax[0, 0].set_ylabel("Rs")
        ax[0, 0].grid(alpha=0.3)

        # 2) pie chart: share of each category
        ax[0, 1].pie(c_tot, labels=c_names, autopct="%1.1f%%", startangle=90)
        ax[0, 1].set_title("Spending by category")

        # 3) bar plot: category comparison
        order = np.argsort(c_tot)[::-1]
        ax[1, 0].bar(c_names[order], c_tot[order], color="tab:orange")
        ax[1, 0].set_title("Category-wise total")
        ax[1, 0].set_ylabel("Rs")
        ax[1, 0].tick_params(axis="x", rotation=40)

        # 4) cumulative spending over time (np.cumsum)
        dates = np.array([e.date for e in self.expenses], dtype="datetime64[D]")
        idx = np.argsort(dates)
        ax[1, 1].plot(dates[idx], np.cumsum(amounts[idx]), color="tab:green")
        ax[1, 1].fill_between(dates[idx], np.cumsum(amounts[idx]), alpha=0.25, color="tab:green")
        ax[1, 1].set_title("Cumulative spending")
        ax[1, 1].set_ylabel("Rs")
        ax[1, 1].tick_params(axis="x", rotation=30)
        ax[1, 1].grid(alpha=0.3)

        fig.tight_layout(rect=(0, 0, 1, 0.95))

    def plot_dashboard(self, save_as="expense_dashboard.png"):
        if not self.expenses:
            print("Nothing to plot yet.")
            return
        fig = plt.figure(figsize=(13, 9))
        self.draw_on(fig)
        fig.savefig(save_as, dpi=130)
        print(f"Dashboard saved as {save_as}")
        plt.show()

    # ---------------- sample data ----------------
    def load_sample(self, days=90, seed=7):
        rng = random.Random(seed)
        ranges = {"Food": (60, 450), "Travel": (30, 600), "Shopping": (300, 3000), "Bills": (200, 1500),
                  "Entertainment": (100, 800), "Education": (100, 1200), "Health": (100, 900), "Other": (50, 500)}
        weights = [30, 18, 10, 6, 12, 8, 6, 10]
        notes = {"Food": "Canteen / snacks", "Travel": "Bus / auto", "Shopping": "Clothes / accessories",
                 "Bills": "Recharge / bill", "Entertainment": "Movie / outing", "Education": "Books / course",
                 "Health": "Medicines", "Other": "Miscellaneous"}
        start = date.today() - timedelta(days=days)
        for d in range(days + 1):
            day = start + timedelta(days=d)
            for _ in range(rng.choice([0, 1, 1, 2, 3])):
                c = rng.choices(CATEGORIES, weights)[0]
                lo, hi = ranges[c]
                self.expenses.append(Expense(day.isoformat(), c, round(rng.uniform(lo, hi), 2), notes[c]))
        self.expenses.append(RecurringExpense(start.isoformat(), "Entertainment", 199, "OTT subscription", "Monthly"))
        self.expenses.append(RecurringExpense(start.isoformat(), "Food", 3500, "Mess fee", "Monthly"))
        self.save()


# =====================================================================
#  COMMAND-LINE INTERFACE
# =====================================================================
def ask_date():
    while True:
        text = input("Date (YYYY-MM-DD) [Enter = today]: ").strip()
        if not text:
            return date.today().isoformat()
        try:
            return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
        except ValueError:
            print("Invalid date. Example: 2026-10-25")


def ask_category():
    for i, c in enumerate(CATEGORIES, 1):
        print(f"  {i}. {c}")
    while True:
        text = input("Choose category number: ").strip()
        if text.isdigit() and 1 <= int(text) <= len(CATEGORIES):
            return CATEGORIES[int(text) - 1]
        print("Please enter a number from the list.")


def ask_amount(prompt="Amount (Rs): "):
    while True:
        try:
            value = float(input(prompt))
            if value > 0:
                return value
        except ValueError:
            pass
        print("Enter a number greater than 0.")


def show(expenses):
    if not expenses:
        print("No expenses found.")
        return
    print(f"\n{'No.':<4} {'Date':<10} | {'Category':<13} | {'Amount':>12} | Note")
    for i, e in enumerate(expenses, 1):
        print(f"{i:<4} {e.describe()}")


def main():
    tracker = ExpenseTracker()
    while True:
        print("\n" + "=" * 40)
        print("        EXPENSE TRACKER")
        print("=" * 40)
        print("1. Add expense")
        print("2. Add recurring expense")
        print("3. View all expenses")
        print("4. Delete an expense")
        print("5. Search (category / note / month like 2026-10)")
        print("6. Summary (NumPy analysis)")
        print("7. Set / check monthly budget")
        print("8. Show charts")
        print("9. Load sample data")
        print("0. Exit")
        try:
            choice = input("Choice: ").strip()

            if choice == "1":
                d, c = ask_date(), ask_category()
                a = ask_amount()
                tracker.add(Expense(d, c, a, input("Note: ").strip()))
                print("Expense added.")
            elif choice == "2":
                d, c = ask_date(), ask_category()
                a = ask_amount()
                note = input("Note: ").strip()
                freq = "Weekly" if input("Frequency: 1) Monthly  2) Weekly : ").strip() == "2" else "Monthly"
                tracker.add(RecurringExpense(d, c, a, note, freq))
                print("Recurring expense added.")
            elif choice == "3":
                show(tracker.sorted_expenses())
            elif choice == "4":
                show(tracker.sorted_expenses())
                n = input("Number to delete: ").strip()
                gone = tracker.delete(int(n)) if n.isdigit() else None
                print("Deleted: " + gone.describe() if gone else "Invalid number.")
            elif choice == "5":
                show(tracker.search(input("Search text: ")))
            elif choice == "6":
                tracker.summary()
            elif choice == "7":
                if input("Set new budget? (y/n): ").strip().lower() == "y":
                    tracker.budget = ask_amount("Monthly budget (Rs): ")
                    tracker.save()
                tracker.check_budget()
            elif choice == "8":
                tracker.plot_dashboard()
            elif choice == "9":
                tracker.load_sample()
                print(f"Sample data added. Total expenses now: {len(tracker.expenses)}")
            elif choice == "0":
                print("Bye!")
                break
            else:
                print("Invalid choice.")
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break


if __name__ == "__main__":
    main()