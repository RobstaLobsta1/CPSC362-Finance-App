"""Simplified Tkinter interface for the Finance Tracker App."""

import calendar
from datetime import date, datetime
import tkinter as tk
from tkinter import messagebox, ttk

from balance_manager import calculate_balances, generate_settlement_suggestions
from models import Expense, Group, Peer, Settlement, new_id, parse_date, validate_expense
from storage import ensure_data_files, load_all, save_records


class CalendarPopup(tk.Toplevel):
    """Small calendar picker used by all date fields."""

    def __init__(self, parent, date_var):
        super().__init__(parent)
        self.date_var = date_var
        self.title("Pick a date")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        try:
            selected = datetime.strptime(date_var.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            selected = date.today()
        self.year = selected.year
        self.month = selected.month

        self.header_var = tk.StringVar()
        self.days_frame = ttk.Frame(self)
        self.build()
        self.render_month()

    def build(self):
        nav = ttk.Frame(self)
        nav.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Button(nav, text="<", width=3, command=self.previous_month).pack(side="left")
        ttk.Label(nav, textvariable=self.header_var, width=20, anchor="center").pack(side="left", expand=True)
        ttk.Button(nav, text=">", width=3, command=self.next_month).pack(side="right")
        self.days_frame.pack(padx=10, pady=6)
        ttk.Button(self, text="Today", command=lambda: self.pick(date.today())).pack(fill="x", padx=10, pady=(0, 10))

    def render_month(self):
        for widget in self.days_frame.winfo_children():
            widget.destroy()
        self.header_var.set(f"{calendar.month_name[self.month]} {self.year}")
        for column, day_name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            ttk.Label(self.days_frame, text=day_name, width=5, anchor="center").grid(row=0, column=column, pady=2)
        for row, week in enumerate(calendar.monthcalendar(self.year, self.month), start=1):
            for column, day_number in enumerate(week):
                if day_number:
                    ttk.Button(
                        self.days_frame,
                        text=str(day_number),
                        width=5,
                        command=lambda day=day_number: self.pick(date(self.year, self.month, day)),
                    ).grid(row=row, column=column, padx=1, pady=1)
                else:
                    ttk.Label(self.days_frame, text="", width=5).grid(row=row, column=column, padx=1, pady=1)

    def previous_month(self):
        self.month -= 1
        if self.month == 0:
            self.month = 12
            self.year -= 1
        self.render_month()

    def next_month(self):
        self.month += 1
        if self.month == 13:
            self.month = 1
            self.year += 1
        self.render_month()

    def pick(self, selected_date):
        self.date_var.set(selected_date.isoformat())
        self.destroy()


class FinanceTrackerApp(tk.Tk):
    """Main app window with a simple student-friendly workflow."""

    def __init__(self):
        super().__init__()
        self.title("Finance Tracker App")
        self.geometry("1060x700")
        self.minsize(900, 620)

        ensure_data_files()
        self.data = load_all()
        self.selected_expense_id = None
        self.selected_peer_id = None
        self.selected_group_id = None

        self.participant_vars = {}
        self.custom_split_vars = {}
        self.group_member_vars = {}
        self.peer_value_ids = {}
        self.group_value_ids = {}
        self.expense_value_ids = {}

        self.build_styles()
        self.build_layout()
        self.refresh_all()

    # Major section: app shell and shared helpers.
    def build_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TButton", padding=6)
        self.style.configure("Treeview", rowheight=27)
        self.style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        self.style.configure("Hint.TLabel", foreground="#555555")

    def build_layout(self):
        ttk.Label(self, text="Finance Tracker", style="Title.TLabel").pack(anchor="w", padx=16, pady=(12, 2))
        ttk.Label(
            self,
            text="Add expenses, check who owes what, and record payments.",
            style="Hint.TLabel",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.expenses_tab = ttk.Frame(self.notebook)
        self.balances_tab = ttk.Frame(self.notebook)
        self.people_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.expenses_tab, text="Expenses")
        self.notebook.add(self.balances_tab, text="Balances")
        self.notebook.add(self.people_tab, text="People")

        self.build_expenses_tab()
        self.build_balances_tab()
        self.build_people_tab()

    def add_date_field(self, parent, variable, row, column):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=column, sticky="w", padx=8, pady=5)
        ttk.Entry(frame, textvariable=variable, width=14).pack(side="left")
        ttk.Button(frame, text="Pick", command=lambda: CalendarPopup(self, variable)).pack(side="left", padx=(4, 0))

    def display_values(self, records, label_func, blank_label=None):
        """Return readable dropdown labels and a hidden label-to-id map."""
        values = []
        value_ids = {}
        label_counts = {}
        for record in records:
            label = label_func(record)
            label_counts[label] = label_counts.get(label, 0) + 1
            display = label if label_counts[label] == 1 else f"{label} #{label_counts[label]}"
            values.append(display)
            value_ids[display] = record["id"]
        return ([blank_label] if blank_label else []) + values, value_ids

    def peer_name(self, peer_id):
        peer = next((item for item in self.data["peers"] if item["id"] == peer_id), None)
        return peer["name"] if peer else "Unknown"

    def group_name(self, group_id):
        if not group_id:
            return ""
        group = next((item for item in self.data["groups"] if item["id"] == group_id), None)
        return group["name"] if group else "Unknown"

    def selected_tree_id(self, tree):
        selection = tree.selection()
        return selection[0] if selection else None

    def refresh_all(self):
        self.refresh_people()
        self.refresh_expense_controls()
        self.refresh_expenses()
        self.refresh_balance_controls()
        self.refresh_balances()
        self.refresh_settlements()

    # Major section: expenses.
    def build_expenses_tab(self):
        left = ttk.LabelFrame(self.expenses_tab, text="Add or Edit Expense")
        left.pack(side="left", fill="y", padx=(0, 12), pady=8)

        self.expense_amount_var = tk.StringVar()
        self.expense_date_var = tk.StringVar(value=date.today().isoformat())
        self.expense_description_var = tk.StringVar()
        self.expense_payer_var = tk.StringVar()
        self.expense_group_var = tk.StringVar(value="No group")
        self.split_type_var = tk.StringVar(value="equal")

        ttk.Label(left, text="Amount").grid(row=0, column=0, sticky="w", padx=8, pady=5)
        ttk.Entry(left, textvariable=self.expense_amount_var, width=28).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Label(left, text="Date").grid(row=1, column=0, sticky="w", padx=8, pady=5)
        self.add_date_field(left, self.expense_date_var, 1, 1)
        ttk.Label(left, text="What was it?").grid(row=2, column=0, sticky="w", padx=8, pady=5)
        ttk.Entry(left, textvariable=self.expense_description_var, width=28).grid(row=2, column=1, sticky="ew", padx=8, pady=5)

        ttk.Label(left, text="Paid by").grid(row=3, column=0, sticky="w", padx=8, pady=5)
        self.payer_combo = ttk.Combobox(left, textvariable=self.expense_payer_var, state="readonly", width=25)
        self.payer_combo.grid(row=3, column=1, sticky="ew", padx=8, pady=5)

        ttk.Label(left, text="Group").grid(row=4, column=0, sticky="w", padx=8, pady=5)
        self.expense_group_combo = ttk.Combobox(left, textvariable=self.expense_group_var, state="readonly", width=25)
        self.expense_group_combo.grid(row=4, column=1, sticky="ew", padx=8, pady=5)
        self.expense_group_combo.bind("<<ComboboxSelected>>", self.apply_group_to_expense)

        ttk.Label(left, text="Split").grid(row=5, column=0, sticky="w", padx=8, pady=5)
        split_row = ttk.Frame(left)
        split_row.grid(row=5, column=1, sticky="w", padx=8, pady=5)
        ttk.Radiobutton(split_row, text="Equally", variable=self.split_type_var, value="equal", command=self.refresh_custom_splits).pack(side="left")
        ttk.Radiobutton(split_row, text="Custom", variable=self.split_type_var, value="custom", command=self.refresh_custom_splits).pack(side="left", padx=(8, 0))

        self.participants_box = ttk.LabelFrame(left, text="Split With")
        self.participants_box.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        self.custom_box = ttk.LabelFrame(left, text="Custom Amounts")
        self.custom_box.grid(row=7, column=0, columnspan=2, sticky="ew", padx=8, pady=8)

        ttk.Button(left, text="Save Expense", command=self.save_expense).grid(row=8, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
        ttk.Button(left, text="Clear Form", command=self.clear_expense_form).grid(row=9, column=0, sticky="ew", padx=8, pady=4)
        ttk.Button(left, text="Delete Selected", command=self.delete_expense).grid(row=9, column=1, sticky="ew", padx=8, pady=4)

        right = ttk.Frame(self.expenses_tab)
        right.pack(side="left", fill="both", expand=True, pady=8)
        filter_bar = ttk.LabelFrame(right, text="History")
        filter_bar.pack(fill="x", pady=(0, 8))

        self.filter_peer_var = tk.StringVar(value="Everyone")
        self.filter_group_var = tk.StringVar(value="All groups")
        self.filter_start_var = tk.StringVar()
        self.filter_end_var = tk.StringVar()
        self.filter_peer_combo = ttk.Combobox(filter_bar, textvariable=self.filter_peer_var, state="readonly", width=20)
        self.filter_group_combo = ttk.Combobox(filter_bar, textvariable=self.filter_group_var, state="readonly", width=20)

        ttk.Label(filter_bar, text="Person").grid(row=0, column=0, padx=6, pady=6)
        self.filter_peer_combo.grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(filter_bar, text="Group").grid(row=0, column=2, padx=6, pady=6)
        self.filter_group_combo.grid(row=0, column=3, padx=6, pady=6)
        ttk.Label(filter_bar, text="From").grid(row=1, column=0, padx=6, pady=6)
        self.add_date_field(filter_bar, self.filter_start_var, 1, 1)
        ttk.Label(filter_bar, text="To").grid(row=1, column=2, padx=6, pady=6)
        self.add_date_field(filter_bar, self.filter_end_var, 1, 3)
        ttk.Button(filter_bar, text="Apply", command=self.refresh_expenses).grid(row=0, column=4, padx=6, pady=6)
        ttk.Button(filter_bar, text="Reset", command=self.reset_expense_filters).grid(row=1, column=4, padx=6, pady=6)

        columns = ("date", "description", "amount", "payer", "group", "split_with")
        self.expenses_tree = ttk.Treeview(right, columns=columns, show="headings")
        headings = {
            "date": "Date",
            "description": "Expense",
            "amount": "Amount",
            "payer": "Paid By",
            "group": "Group",
            "split_with": "Split With",
        }
        for column, text in headings.items():
            self.expenses_tree.heading(column, text=text)
        self.expenses_tree.column("description", width=180)
        self.expenses_tree.column("split_with", width=220)
        self.expenses_tree.pack(fill="both", expand=True)
        self.expenses_tree.bind("<<TreeviewSelect>>", self.on_expense_select)

    def refresh_expense_controls(self):
        peer_values, self.peer_value_ids = self.display_values(
            sorted(self.data["peers"], key=lambda item: item["name"].lower()),
            lambda peer: peer["name"],
        )
        group_values, self.group_value_ids = self.display_values(
            sorted(self.data["groups"], key=lambda item: item["name"].lower()),
            lambda group: group["name"],
            blank_label="No group",
        )
        self.payer_combo["values"] = peer_values
        self.expense_group_combo["values"] = group_values
        self.filter_peer_combo["values"] = ["Everyone"] + peer_values
        self.filter_group_combo["values"] = ["All groups"] + group_values[1:]

        if peer_values and not self.expense_payer_var.get():
            self.expense_payer_var.set(peer_values[0])
        if not self.expense_group_var.get():
            self.expense_group_var.set("No group")
        if self.filter_peer_var.get() not in self.filter_peer_combo["values"]:
            self.filter_peer_var.set("Everyone")
        if self.filter_group_var.get() not in self.filter_group_combo["values"]:
            self.filter_group_var.set("All groups")

        for frame in (self.participants_box, self.custom_box):
            for widget in frame.winfo_children():
                widget.destroy()
        self.participant_vars = {}
        self.custom_split_vars = {}

        for peer in sorted(self.data["peers"], key=lambda item: item["name"].lower()):
            participant_var = tk.BooleanVar()
            ttk.Checkbutton(
                self.participants_box,
                text=peer["name"],
                variable=participant_var,
                command=self.refresh_custom_splits,
            ).pack(anchor="w", padx=6, pady=2)
            self.participant_vars[peer["id"]] = participant_var

            row = ttk.Frame(self.custom_box)
            row.pack(fill="x", padx=6, pady=2)
            ttk.Label(row, text=peer["name"], width=18).pack(side="left")
            amount_var = tk.StringVar(value="0.00")
            ttk.Entry(row, textvariable=amount_var, width=10).pack(side="left")
            self.custom_split_vars[peer["id"]] = amount_var
        self.refresh_custom_splits()

    def refresh_custom_splits(self):
        use_custom = self.split_type_var.get() == "custom"
        for row in self.custom_box.winfo_children():
            label = row.winfo_children()[0]
            entry = row.winfo_children()[1]
            peer_name = label.cget("text")
            peer_id = next((peer["id"] for peer in self.data["peers"] if peer["name"] == peer_name), "")
            enabled = use_custom and self.participant_vars.get(peer_id, tk.BooleanVar()).get()
            entry.configure(state="normal" if enabled else "disabled")

    def apply_group_to_expense(self, _event=None):
        group_id = self.group_value_ids.get(self.expense_group_var.get(), "")
        group = next((item for item in self.data["groups"] if item["id"] == group_id), None)
        if not group:
            return
        for peer_id, var in self.participant_vars.items():
            var.set(peer_id in group["peer_ids"])
        payer_id = self.peer_value_ids.get(self.expense_payer_var.get(), "")
        if payer_id not in group["peer_ids"] and group["peer_ids"]:
            for value in self.payer_combo["values"]:
                if self.peer_value_ids.get(value) == group["peer_ids"][0]:
                    self.expense_payer_var.set(value)
                    break
        self.refresh_custom_splits()

    def expense_form_data(self):
        participants = [peer_id for peer_id, var in self.participant_vars.items() if var.get()]
        custom_splits = {peer_id: var.get().strip() for peer_id, var in self.custom_split_vars.items()}
        return {
            "amount": self.expense_amount_var.get(),
            "date": self.expense_date_var.get(),
            "description": self.expense_description_var.get(),
            "payer_id": self.peer_value_ids.get(self.expense_payer_var.get(), ""),
            "participant_ids": participants,
            "split_type": self.split_type_var.get(),
            "custom_splits": custom_splits,
            "group_id": self.group_value_ids.get(self.expense_group_var.get(), ""),
        }

    def save_expense(self):
        try:
            data = validate_expense(self.expense_form_data(), self.data["peers"], self.data["groups"])
        except ValueError as exc:
            messagebox.showerror("Cannot save expense", str(exc))
            return
        if self.selected_expense_id:
            for expense in self.data["expenses"]:
                if expense["id"] == self.selected_expense_id:
                    expense.update(data)
                    break
        else:
            self.data["expenses"].append(Expense(**data).to_dict())
        save_records("expenses", self.data["expenses"])
        self.clear_expense_form()
        self.refresh_all()

    def delete_expense(self):
        if not self.selected_expense_id:
            messagebox.showinfo("Choose an expense", "Select an expense from the history first.")
            return
        self.data["expenses"] = [expense for expense in self.data["expenses"] if expense["id"] != self.selected_expense_id]
        save_records("expenses", self.data["expenses"])
        self.clear_expense_form()
        self.refresh_all()

    def clear_expense_form(self):
        self.selected_expense_id = None
        self.expense_amount_var.set("")
        self.expense_date_var.set(date.today().isoformat())
        self.expense_description_var.set("")
        peer_values = list(self.payer_combo["values"])
        self.expense_payer_var.set(peer_values[0] if peer_values else "")
        self.expense_group_var.set("No group")
        self.split_type_var.set("equal")
        for var in self.participant_vars.values():
            var.set(False)
        for var in self.custom_split_vars.values():
            var.set("0.00")
        self.expenses_tree.selection_remove(self.expenses_tree.selection())
        self.refresh_custom_splits()

    def on_expense_select(self, _event=None):
        expense_id = self.selected_tree_id(self.expenses_tree)
        if not expense_id:
            return
        expense = next(item for item in self.data["expenses"] if item["id"] == expense_id)
        self.selected_expense_id = expense_id
        self.expense_amount_var.set(f"{float(expense['amount']):.2f}")
        self.expense_date_var.set(expense["date"])
        self.expense_description_var.set(expense["description"])
        self.expense_payer_var.set(next(value for value in self.payer_combo["values"] if self.peer_value_ids.get(value) == expense["payer_id"]))
        self.expense_group_var.set("No group")
        if expense.get("group_id"):
            for value in self.expense_group_combo["values"]:
                if self.group_value_ids.get(value) == expense["group_id"]:
                    self.expense_group_var.set(value)
                    break
        self.split_type_var.set(expense["split_type"])
        for peer_id, var in self.participant_vars.items():
            var.set(peer_id in expense["participant_ids"])
        for peer_id, var in self.custom_split_vars.items():
            var.set(f"{float(expense.get('custom_splits', {}).get(peer_id, 0)):.2f}")
        self.refresh_custom_splits()

    def reset_expense_filters(self):
        self.filter_peer_var.set("Everyone")
        self.filter_group_var.set("All groups")
        self.filter_start_var.set("")
        self.filter_end_var.set("")
        self.refresh_expenses()

    def expense_matches_filters(self, expense):
        peer_id = self.peer_value_ids.get(self.filter_peer_var.get(), "")
        group_id = self.group_value_ids.get(self.filter_group_var.get(), "")
        if peer_id and peer_id != expense["payer_id"] and peer_id not in expense["participant_ids"]:
            return False
        if group_id and expense.get("group_id") != group_id:
            return False
        if self.filter_start_var.get().strip() and expense["date"] < parse_date(self.filter_start_var.get()):
            return False
        if self.filter_end_var.get().strip() and expense["date"] > parse_date(self.filter_end_var.get()):
            return False
        return True

    def refresh_expenses(self):
        self.expenses_tree.delete(*self.expenses_tree.get_children())
        try:
            expenses = [expense for expense in self.data["expenses"] if self.expense_matches_filters(expense)]
        except ValueError as exc:
            messagebox.showerror("Bad filter", str(exc))
            return
        for expense in sorted(expenses, key=lambda item: item["date"], reverse=True):
            participants = ", ".join(self.peer_name(peer_id) for peer_id in expense["participant_ids"])
            self.expenses_tree.insert(
                "",
                "end",
                iid=expense["id"],
                values=(
                    expense["date"],
                    expense["description"],
                    f"${float(expense['amount']):.2f}",
                    self.peer_name(expense["payer_id"]),
                    self.group_name(expense.get("group_id", "")),
                    participants,
                ),
            )

    # Major section: balances, suggestions, and payments.
    def build_balances_tab(self):
        top = ttk.LabelFrame(self.balances_tab, text="Show Balances For")
        top.pack(fill="x", pady=8)

        self.balance_scope_var = tk.StringVar(value="All expenses")
        self.balance_group_var = tk.StringVar()
        self.balance_expense_var = tk.StringVar()
        ttk.Label(top, text="View").grid(row=0, column=0, padx=8, pady=8)
        self.balance_scope_combo = ttk.Combobox(
            top,
            textvariable=self.balance_scope_var,
            values=("All expenses", "One group", "One expense"),
            state="readonly",
            width=16,
        )
        self.balance_scope_combo.grid(row=0, column=1, padx=8, pady=8)
        self.balance_scope_combo.bind("<<ComboboxSelected>>", self.on_balance_scope_change)
        self.balance_group_combo = ttk.Combobox(top, textvariable=self.balance_group_var, state="readonly", width=26)
        self.balance_group_combo.grid(row=0, column=2, padx=8, pady=8)
        self.balance_group_combo.configure(postcommand=self.refresh_balance_controls)
        self.balance_group_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_balances())
        self.balance_expense_combo = ttk.Combobox(top, textvariable=self.balance_expense_var, state="readonly", width=48)
        self.balance_expense_combo.grid(row=0, column=3, padx=8, pady=8)
        self.balance_expense_combo.configure(postcommand=self.refresh_balance_controls)
        self.balance_expense_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_balances())
        ttk.Button(top, text="Refresh View", command=self.refresh_balances).grid(row=0, column=4, padx=8, pady=8)

        self.balance_summary_var = tk.StringVar()
        ttk.Label(self.balances_tab, textvariable=self.balance_summary_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))

        body = ttk.Frame(self.balances_tab)
        body.pack(fill="both", expand=True)

        left = ttk.LabelFrame(body, text="Who Owes What")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        columns = ("person", "status")
        self.balances_tree = ttk.Treeview(left, columns=columns, show="headings", height=10)
        self.balances_tree.heading("person", text="Person")
        self.balances_tree.heading("status", text="Balance")
        self.balances_tree.column("person", width=170)
        self.balances_tree.column("status", width=260)
        self.balances_tree.pack(fill="both", expand=True, padx=8, pady=8)

        right = ttk.LabelFrame(body, text="Suggested Payments")
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.suggestions_list = tk.Listbox(right, height=10)
        self.suggestions_list.pack(fill="both", expand=True, padx=8, pady=8)
        self.suggestions_list.bind("<<ListboxSelect>>", self.use_selected_suggestion)

        payment_box = ttk.LabelFrame(self.balances_tab, text="Record a Payment")
        payment_box.pack(fill="x", pady=(8, 0))
        self.pay_from_var = tk.StringVar()
        self.pay_to_var = tk.StringVar()
        self.pay_amount_var = tk.StringVar()
        self.pay_date_var = tk.StringVar(value=date.today().isoformat())
        self.pay_note_var = tk.StringVar()
        self.pay_from_combo = ttk.Combobox(payment_box, textvariable=self.pay_from_var, state="readonly", width=24)
        self.pay_to_combo = ttk.Combobox(payment_box, textvariable=self.pay_to_var, state="readonly", width=24)
        ttk.Label(payment_box, text="From").grid(row=0, column=0, padx=6, pady=6)
        self.pay_from_combo.grid(row=0, column=1, padx=6, pady=6)
        self.pay_from_combo.bind("<<ComboboxSelected>>", self.on_payment_from_change)
        ttk.Label(payment_box, text="To").grid(row=0, column=2, padx=6, pady=6)
        self.pay_to_combo.grid(row=0, column=3, padx=6, pady=6)
        self.pay_to_combo.bind("<<ComboboxSelected>>", self.on_payment_to_change)
        ttk.Label(payment_box, text="Amount").grid(row=0, column=4, padx=6, pady=6)
        ttk.Entry(payment_box, textvariable=self.pay_amount_var, width=12).grid(row=0, column=5, padx=6, pady=6)
        ttk.Label(payment_box, text="Date").grid(row=1, column=0, padx=6, pady=6)
        self.add_date_field(payment_box, self.pay_date_var, 1, 1)
        ttk.Label(payment_box, text="Note").grid(row=1, column=2, padx=6, pady=6)
        ttk.Entry(payment_box, textvariable=self.pay_note_var, width=28).grid(row=1, column=3, columnspan=2, padx=6, pady=6)
        ttk.Button(payment_box, text="Save Payment", command=self.record_settlement).grid(row=1, column=5, padx=6, pady=6)
        ttk.Button(payment_box, text="Pay Balance", command=self.pay_selected_balance).grid(row=1, column=6, padx=6, pady=6)

        history_box = ttk.LabelFrame(self.balances_tab, text="Payment History")
        history_box.pack(fill="both", expand=True, pady=(8, 0))
        columns = ("date", "payment", "note")
        self.settlements_tree = ttk.Treeview(history_box, columns=columns, show="headings", height=5)
        self.settlements_tree.heading("date", text="Date")
        self.settlements_tree.heading("payment", text="Payment")
        self.settlements_tree.heading("note", text="Note")
        self.settlements_tree.column("payment", width=360)
        self.settlements_tree.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        ttk.Button(history_box, text="Undo Selected Payment", command=self.undo_settlement).pack(side="left", padx=8, pady=8)

    def refresh_balance_controls(self):
        group_values, self.group_value_ids = self.display_values(
            sorted(self.data["groups"], key=lambda item: item["name"].lower()),
            lambda group: group["name"],
        )
        expense_values, self.expense_value_ids = self.display_values(
            sorted(self.data["expenses"], key=lambda item: (item["date"], item["description"]), reverse=True),
            lambda expense: f"{expense['date']} - {expense['description']} - ${float(expense['amount']):.2f}",
        )
        peer_values, self.peer_value_ids = self.display_values(
            sorted(self.data["peers"], key=lambda item: item["name"].lower()),
            lambda peer: peer["name"],
        )
        self.balance_group_combo["values"] = group_values
        self.balance_expense_combo["values"] = expense_values
        if group_values and self.balance_group_var.get() not in group_values:
            self.balance_group_var.set(group_values[0])
        if not group_values:
            self.balance_group_var.set("")
        if expense_values and self.balance_expense_var.get() not in expense_values:
            self.balance_expense_var.set(expense_values[0])
        if not expense_values:
            self.balance_expense_var.set("")
        self.refresh_payment_options()
        self.on_balance_scope_change(refresh=False)

    def on_balance_scope_change(self, _event=None, refresh=True):
        scope = self.balance_scope_var.get()
        self.balance_group_combo.configure(state="readonly" if scope == "One group" else "disabled")
        self.balance_expense_combo.configure(state="readonly" if scope == "One expense" else "disabled")
        if refresh:
            self.refresh_balances()

    def balance_expenses(self):
        scope = self.balance_scope_var.get()
        if scope == "One group":
            group_id = self.group_value_ids.get(self.balance_group_var.get(), "")
            return [expense for expense in self.data["expenses"] if expense.get("group_id") == group_id], False
        if scope == "One expense":
            expense_id = self.expense_value_ids.get(self.balance_expense_var.get(), "")
            return [expense for expense in self.data["expenses"] if expense["id"] == expense_id], False
        return list(self.data["expenses"]), True

    def balance_people(self, expenses):
        scope = self.balance_scope_var.get()
        if scope == "One group":
            group_id = self.group_value_ids.get(self.balance_group_var.get(), "")
            group = next((item for item in self.data["groups"] if item["id"] == group_id), None)
            if group:
                group_peer_ids = set(group["peer_ids"])
                return [peer for peer in self.data["peers"] if peer["id"] in group_peer_ids]
        if scope == "One expense" and expenses:
            expense = expenses[0]
            peer_ids = set(expense["participant_ids"])
            peer_ids.add(expense["payer_id"])
            return [peer for peer in self.data["peers"] if peer["id"] in peer_ids]
        return list(self.data["peers"])

    def refresh_balances(self):
        self.balances_tree.delete(*self.balances_tree.get_children())
        self.suggestions_list.delete(0, tk.END)
        self.current_suggestions = []
        expenses, include_settlements = self.balance_expenses()
        peers = self.balance_people(expenses)
        settlements = self.data["settlements"] if include_settlements and expenses else []
        balances = calculate_balances(self.data["peers"], expenses, settlements)
        total_to_move = round(sum(-amount for amount in balances.values() if amount < -0.005), 2)

        if not expenses:
            self.balance_summary_var.set("No expenses in this view. Everyone is settled.")
        elif total_to_move <= 0.005:
            self.balance_summary_var.set("Everyone is settled for this view.")
        else:
            note = "Payments are included." if include_settlements else "Payments are hidden here so this filtered view stays simple."
            self.balance_summary_var.set(f"${total_to_move:.2f} still needs to move. {note}")

        for peer in sorted(peers, key=lambda item: item["name"].lower()):
            amount = balances.get(peer["id"], 0.0)
            if amount > 0.005:
                status = f"gets back ${amount:.2f}"
            elif amount < -0.005:
                status = f"owes ${abs(amount):.2f}"
            else:
                status = "settled"
            self.balances_tree.insert("", "end", values=(peer["name"], status))

        suggestions = generate_settlement_suggestions(balances)
        if not suggestions:
            self.suggestions_list.insert(tk.END, "No payments needed.")
            self.refresh_payment_options()
            return
        self.current_suggestions = suggestions
        for suggestion in suggestions:
            self.suggestions_list.insert(
                tk.END,
                f"{self.peer_name(suggestion['from_peer_id'])} pays {self.peer_name(suggestion['to_peer_id'])} ${suggestion['amount']:.2f}",
            )
        self.refresh_payment_options()

    def current_payment_suggestions(self):
        if not self.data["expenses"]:
            return []
        balances = calculate_balances(self.data["peers"], self.data["expenses"], self.data["settlements"])
        return generate_settlement_suggestions(balances)

    def peer_label(self, peer_id):
        for label, value_id in self.peer_value_ids.items():
            if value_id == peer_id:
                return label
        return ""

    def payment_amount_between(self, from_peer_id, to_peer_id):
        for suggestion in self.current_payment_suggestions():
            if suggestion["from_peer_id"] == from_peer_id and suggestion["to_peer_id"] == to_peer_id:
                return round(float(suggestion["amount"]), 2)
        return 0.0

    def refresh_payment_options(self):
        suggestions = self.current_payment_suggestions()
        debtor_ids = []
        for suggestion in suggestions:
            if suggestion["from_peer_id"] not in debtor_ids:
                debtor_ids.append(suggestion["from_peer_id"])

        debtor_labels = [self.peer_label(peer_id) for peer_id in debtor_ids if self.peer_label(peer_id)]
        self.pay_from_combo["values"] = debtor_labels
        if self.pay_from_var.get() not in debtor_labels:
            self.pay_from_var.set(debtor_labels[0] if debtor_labels else "")

        from_peer_id = self.peer_value_ids.get(self.pay_from_var.get(), "")
        creditor_ids = []
        for suggestion in suggestions:
            if suggestion["from_peer_id"] == from_peer_id and suggestion["to_peer_id"] not in creditor_ids:
                creditor_ids.append(suggestion["to_peer_id"])
        creditor_labels = [self.peer_label(peer_id) for peer_id in creditor_ids if self.peer_label(peer_id)]
        self.pay_to_combo["values"] = creditor_labels
        if self.pay_to_var.get() not in creditor_labels:
            self.pay_to_var.set(creditor_labels[0] if creditor_labels else "")

        self.fill_selected_payment_amount()

    def fill_selected_payment_amount(self):
        from_peer_id = self.peer_value_ids.get(self.pay_from_var.get(), "")
        to_peer_id = self.peer_value_ids.get(self.pay_to_var.get(), "")
        amount = self.payment_amount_between(from_peer_id, to_peer_id)
        self.pay_amount_var.set(f"{amount:.2f}" if amount else "")

    def on_payment_from_change(self, _event=None):
        self.refresh_payment_options()

    def on_payment_to_change(self, _event=None):
        self.fill_selected_payment_amount()

    def use_selected_suggestion(self, _event=None):
        selection = self.suggestions_list.curselection()
        if not selection or not hasattr(self, "current_suggestions"):
            return
        suggestion = self.current_suggestions[selection[0]]
        self.pay_from_var.set(self.peer_label(suggestion["from_peer_id"]))
        self.refresh_payment_options()
        self.pay_to_var.set(self.peer_label(suggestion["to_peer_id"]))
        self.pay_amount_var.set(f"{suggestion['amount']:.2f}")

    def record_settlement(self):
        from_peer_id = self.peer_value_ids.get(self.pay_from_var.get(), "")
        to_peer_id = self.peer_value_ids.get(self.pay_to_var.get(), "")
        if not from_peer_id or not to_peer_id or from_peer_id == to_peer_id:
            messagebox.showerror("Cannot save payment", "Choose someone who owes money and who they owe.")
            return
        allowed_amount = self.payment_amount_between(from_peer_id, to_peer_id)
        if allowed_amount <= 0:
            messagebox.showerror("Cannot save payment", "That person does not currently owe the selected person.")
            return
        try:
            amount = round(float(self.pay_amount_var.get()), 2)
            payment_date = parse_date(self.pay_date_var.get())
        except ValueError as exc:
            messagebox.showerror("Cannot save payment", str(exc))
            return
        if amount <= 0:
            messagebox.showerror("Cannot save payment", "Amount must be greater than zero.")
            return
        if amount > allowed_amount:
            messagebox.showerror("Cannot save payment", f"The most they currently owe this person is ${allowed_amount:.2f}.")
            return
        settlement = Settlement(
            id=new_id("settlement"),
            from_peer_id=from_peer_id,
            to_peer_id=to_peer_id,
            amount=amount,
            date=payment_date,
            note=self.pay_note_var.get().strip(),
        )
        self.data["settlements"].append(settlement.to_dict())
        save_records("settlements", self.data["settlements"])
        self.pay_amount_var.set("")
        self.pay_note_var.set("")
        self.refresh_all()

    def pay_selected_balance(self):
        from_peer_id = self.peer_value_ids.get(self.pay_from_var.get(), "")
        if not from_peer_id:
            messagebox.showinfo("No balance to pay", "Choose someone who owes money first.")
            return
        try:
            payment_date = parse_date(self.pay_date_var.get())
        except ValueError as exc:
            messagebox.showerror("Cannot save payment", str(exc))
            return

        payments = [
            suggestion
            for suggestion in self.current_payment_suggestions()
            if suggestion["from_peer_id"] == from_peer_id and suggestion["amount"] > 0
        ]
        if not payments:
            messagebox.showinfo("No balance to pay", "This person is already settled.")
            return

        note = self.pay_note_var.get().strip() or "Paid balance"
        for payment in payments:
            settlement = Settlement(
                id=new_id("settlement"),
                from_peer_id=payment["from_peer_id"],
                to_peer_id=payment["to_peer_id"],
                amount=round(float(payment["amount"]), 2),
                date=payment_date,
                note=note,
            )
            self.data["settlements"].append(settlement.to_dict())
        save_records("settlements", self.data["settlements"])
        self.pay_amount_var.set("")
        self.pay_note_var.set("")
        self.refresh_all()

    def undo_settlement(self):
        settlement_id = self.selected_tree_id(self.settlements_tree)
        if not settlement_id:
            messagebox.showinfo("Choose a payment", "Select a payment from the history first.")
            return
        self.data["settlements"] = [item for item in self.data["settlements"] if item["id"] != settlement_id]
        save_records("settlements", self.data["settlements"])
        self.refresh_all()

    def refresh_settlements(self):
        self.settlements_tree.delete(*self.settlements_tree.get_children())
        for settlement in sorted(self.data["settlements"], key=lambda item: item["date"], reverse=True):
            payment = (
                f"{self.peer_name(settlement['from_peer_id'])} paid "
                f"{self.peer_name(settlement['to_peer_id'])} ${float(settlement['amount']):.2f}"
            )
            self.settlements_tree.insert(
                "",
                "end",
                iid=settlement["id"],
                values=(settlement["date"], payment, settlement.get("note", "")),
            )

    # Major section: people and groups.
    def build_people_tab(self):
        peers_box = ttk.LabelFrame(self.people_tab, text="People")
        peers_box.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=8)

        self.peer_name_var = tk.StringVar()
        ttk.Label(peers_box, text="Name").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(peers_box, textvariable=self.peer_name_var, width=26).grid(row=0, column=1, padx=8, pady=6)
        ttk.Button(peers_box, text="Save Person", command=self.save_peer).grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        ttk.Button(peers_box, text="Delete Selected", command=self.delete_peer).grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=4)

        self.peers_tree = ttk.Treeview(peers_box, columns=("name",), show="headings", height=12)
        self.peers_tree.heading("name", text="Name")
        self.peers_tree.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        self.peers_tree.bind("<<TreeviewSelect>>", self.on_peer_select)
        peers_box.rowconfigure(3, weight=1)
        peers_box.columnconfigure(1, weight=1)

        groups_box = ttk.LabelFrame(self.people_tab, text="Groups")
        groups_box.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)

        self.group_name_var = tk.StringVar()
        ttk.Label(groups_box, text="Group Name").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(groups_box, textvariable=self.group_name_var, width=28).grid(row=0, column=1, padx=8, pady=6)
        self.group_members_box = ttk.LabelFrame(groups_box, text="Members")
        self.group_members_box.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        ttk.Button(groups_box, text="Save Group", command=self.save_group).grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        ttk.Button(groups_box, text="Delete Selected", command=self.delete_group).grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=4)

        self.groups_tree = ttk.Treeview(groups_box, columns=("name", "members"), show="headings", height=12)
        self.groups_tree.heading("name", text="Group")
        self.groups_tree.heading("members", text="Members")
        self.groups_tree.column("members", width=300)
        self.groups_tree.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        self.groups_tree.bind("<<TreeviewSelect>>", self.on_group_select)
        groups_box.rowconfigure(4, weight=1)
        groups_box.columnconfigure(1, weight=1)

    def refresh_people(self):
        self.peers_tree.delete(*self.peers_tree.get_children())
        for peer in sorted(self.data["peers"], key=lambda item: item["name"].lower()):
            self.peers_tree.insert("", "end", iid=peer["id"], values=(peer["name"],))

        for widget in self.group_members_box.winfo_children():
            widget.destroy()
        self.group_member_vars = {}
        for peer in sorted(self.data["peers"], key=lambda item: item["name"].lower()):
            var = tk.BooleanVar()
            ttk.Checkbutton(self.group_members_box, text=peer["name"], variable=var).pack(anchor="w", padx=6, pady=2)
            self.group_member_vars[peer["id"]] = var

        self.groups_tree.delete(*self.groups_tree.get_children())
        for group in sorted(self.data["groups"], key=lambda item: item["name"].lower()):
            members = ", ".join(self.peer_name(peer_id) for peer_id in group["peer_ids"])
            self.groups_tree.insert("", "end", iid=group["id"], values=(group["name"], members))

    def save_peer(self):
        name = self.peer_name_var.get().strip()
        if not name:
            messagebox.showerror("Cannot save person", "Name is required.")
            return
        if self.selected_peer_id:
            for peer in self.data["peers"]:
                if peer["id"] == self.selected_peer_id:
                    peer["name"] = name
                    break
        else:
            self.data["peers"].append(Peer(name=name).to_dict())
        save_records("peers", self.data["peers"])
        self.clear_peer_form()
        self.refresh_all()

    def delete_peer(self):
        if not self.selected_peer_id:
            messagebox.showinfo("Choose a person", "Select a person first.")
            return
        used = any(
            expense["payer_id"] == self.selected_peer_id or self.selected_peer_id in expense["participant_ids"]
            for expense in self.data["expenses"]
        )
        used = used or any(
            settlement["from_peer_id"] == self.selected_peer_id or settlement["to_peer_id"] == self.selected_peer_id
            for settlement in self.data["settlements"]
        )
        if used:
            messagebox.showerror("Cannot delete person", "This person is used by expenses or payments.")
            return
        self.data["peers"] = [peer for peer in self.data["peers"] if peer["id"] != self.selected_peer_id]
        for group in self.data["groups"]:
            group["peer_ids"] = [peer_id for peer_id in group["peer_ids"] if peer_id != self.selected_peer_id]
        save_records("peers", self.data["peers"])
        save_records("groups", self.data["groups"])
        self.clear_peer_form()
        self.refresh_all()

    def clear_peer_form(self):
        self.selected_peer_id = None
        self.peer_name_var.set("")

    def on_peer_select(self, _event=None):
        peer_id = self.selected_tree_id(self.peers_tree)
        if not peer_id:
            return
        peer = next(item for item in self.data["peers"] if item["id"] == peer_id)
        self.selected_peer_id = peer_id
        self.peer_name_var.set(peer["name"])

    def save_group(self):
        name = self.group_name_var.get().strip()
        peer_ids = [peer_id for peer_id, var in self.group_member_vars.items() if var.get()]
        if not name or not peer_ids:
            messagebox.showerror("Cannot save group", "Group name and at least one member are required.")
            return
        if self.selected_group_id:
            for group in self.data["groups"]:
                if group["id"] == self.selected_group_id:
                    group["name"] = name
                    group["peer_ids"] = peer_ids
                    break
        else:
            self.data["groups"].append(Group(name=name, peer_ids=peer_ids).to_dict())
        save_records("groups", self.data["groups"])
        self.clear_group_form()
        self.refresh_all()

    def delete_group(self):
        if not self.selected_group_id:
            messagebox.showinfo("Choose a group", "Select a group first.")
            return
        if any(expense.get("group_id") == self.selected_group_id for expense in self.data["expenses"]):
            messagebox.showerror("Cannot delete group", "This group is used by expenses.")
            return
        self.data["groups"] = [group for group in self.data["groups"] if group["id"] != self.selected_group_id]
        save_records("groups", self.data["groups"])
        self.clear_group_form()
        self.refresh_all()

    def clear_group_form(self):
        self.selected_group_id = None
        self.group_name_var.set("")
        for var in self.group_member_vars.values():
            var.set(False)

    def on_group_select(self, _event=None):
        group_id = self.selected_tree_id(self.groups_tree)
        if not group_id:
            return
        group = next(item for item in self.data["groups"] if item["id"] == group_id)
        self.selected_group_id = group_id
        self.group_name_var.set(group["name"])
        for peer_id, var in self.group_member_vars.items():
            var.set(peer_id in group["peer_ids"])
