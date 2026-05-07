"""Application entry point for Finance Tracker App."""

from gui import FinanceTrackerApp


def main():
    """Start the Tkinter desktop application."""
    app = FinanceTrackerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
