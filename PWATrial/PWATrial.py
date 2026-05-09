import os
import reflex as rx

from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# =========================================================
# LOAD ENV
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

print("BASE_DIR =", BASE_DIR)
print("ENV_FILE =", ENV_FILE)
print("ENV EXISTS =", ENV_FILE.exists())

load_dotenv(dotenv_path=ENV_FILE)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("SUPABASE_URL =", SUPABASE_URL)

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL not found")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY not found")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)
# =========================================================
# STATE
# =========================================================

UNITS = [
    "INV 0.5PK",
    "INV 0.75PK",
    "INV 1PK",
    "INV 1.5PK",
    "INV 2PK",
    "INV 2.5PK",
    "NON INV 0.5PK",
    "NON INV 0.75PK",
    "NON INV 1PK",
    "NON INV 1.5PK",
    "NON INV 2PK",
    "NON INV 2.5PK",
]


class State(rx.State):

    summary_data: list[dict] = []

    timeseries_data: list[dict] = []

    selected_unit: str = "INV 0.5PK"

    is_loading: bool = False

    def fetch_all_data(self):

        self.is_loading = True

        try:

            # Summary
            res_sum = (
                supabase
                .table("ac_summary_data")
                .select("*")
                .execute()
            )

            self.summary_data = res_sum.data

            # Timeseries
            self.get_timeseries()

        except Exception as e:
            print(f"Error: {e}")

        finally:
            self.is_loading = False

    def set_selected_unit(self, value: str):

        self.selected_unit = value

        self.get_timeseries()

    def get_timeseries(self):

        try:

            res = (
                supabase
                .table("ac_timeseries_data")
                .select("*")
                .eq("Unit", self.selected_unit)
                .order("Timestamp")
                .limit(500)
                .execute()
            )

            cleaned_data = []

            for r in res.data:

                try:

                    cleaned_data.append(
                        {
                            "time": str(r["Timestamp"])[:16].replace("T", " "),
                            "Wattage": float(r["Avg_Wattage"] or 0),
                            "Voltage": float(r["Avg_Voltage"] or 0),
                            "Current": float(r["Avg_Current"] or 0),
                            "Condition": str(r["Condition"] or "UNKNOWN"),
                        }
                    )

                except Exception:
                    continue

            self.timeseries_data = cleaned_data

            print(
                f"Updated: {self.selected_unit} "
                f"- {len(self.timeseries_data)} rows."
            )

        except Exception as e:
            print(f"Fetch Error: {e}")

    @rx.var
    def filtered_summary(self) -> list[dict]:

        return [
            r for r in self.summary_data
            if r.get("Unit") == self.selected_unit
        ]


# =========================================================
# COMPONENTS
# =========================================================

def condition_badge(condition):

    color = rx.match(
        condition,
        ("NORMAL", "green"),
        ("ABNORMAL", "red"),
        ("MAINTENANCE 1", "orange"),
        ("MAINTENANCE 2", "orange"),
        "gray"
    )

    return rx.badge(
        condition,
        color_scheme=color
    )


def kpi_card(label, value, icon):

    return rx.card(
        rx.vstack(

            rx.hstack(
                rx.icon(tag=icon, size=18),
                rx.text(
                    label,
                    size="2",
                    color="gray"
                ),
            ),

            rx.heading(
                value,
                size="6"
            ),

            align_items="start",
        ),

        width="100%",
    )


# =========================================================
# PAGE
# =========================================================

def index():

    return rx.container(

        rx.vstack(

            # HEADER
            rx.hstack(

                rx.heading(
                    "AC FDD Hub",
                    size="8",
                    color_scheme="blue"
                ),

                rx.spacer(),

                rx.cond(
                    State.is_loading,
                    rx.spinner(size="3")
                ),

                width="100%",
                align_items="center",
                padding_y="4",
            ),

            # KPI GRID
            rx.grid(

                kpi_card(
                    "Total Rows",
                    "115,248",
                    "database"
                ),

                kpi_card(
                    "Active Units",
                    "12",
                    "cpu"
                ),

                kpi_card(
                    "Current Selection",
                    State.selected_unit,
                    "info"
                ),

                columns=rx.breakpoints(
                    initial="1",
                    sm="2",
                    md="3",
                ),

                spacing="4",
                width="100%",
            ),

            # CONTROLS
            rx.card(

                rx.vstack(

                    rx.text(
                        "Select Analysis Unit",
                        font_weight="bold"
                    ),

                    rx.select(
                        UNITS,
                        value=State.selected_unit,
                        on_change=State.set_selected_unit,
                        width="100%",
                    ),

                    width="100%",
                    spacing="3",
                    align_items="start",
                ),

                width="100%",
            ),

            # CHART
            rx.card(

                rx.vstack(

                    rx.heading(
                        f"Wattage Trend: {State.selected_unit}",
                        size="4"
                    ),

                    rx.recharts.line_chart(

                        rx.recharts.line(
                            data_key="Wattage",
                            stroke="#3b82f6",
                            dot=False,
                        ),

                        rx.recharts.x_axis(
                            data_key="time"
                        ),

                        rx.recharts.y_axis(),

                        rx.recharts.graphing_tooltip(),

                        data=State.timeseries_data,

                        width="100%",
                        height=300,
                    ),

                    width="100%",
                ),

                width="100%",
            ),

            # TABLE
            rx.card(

                rx.vstack(

                    rx.heading(
                        "Diagnostic Breakdown",
                        size="4"
                    ),

                    rx.table.root(

                        rx.table.header(

                            rx.table.row(

                                rx.table.column_header_cell("Status"),

                                rx.table.column_header_cell(
                                    "Avg Wattage"
                                ),

                                rx.table.column_header_cell(
                                    "Avg Voltage"
                                ),
                            )
                        ),

                        rx.table.body(

                            rx.foreach(

                                State.filtered_summary,

                                lambda r: rx.table.row(

                                    rx.table.cell(
                                        condition_badge(
                                            r["Condition"]
                                        )
                                    ),

                                    rx.table.cell(
                                        f"{r['Avg_Wattage']} W"
                                    ),

                                    rx.table.cell(
                                        f"{r['Avg_Voltage']} V"
                                    ),
                                )
                            )
                        ),

                        width="100%",
                    ),

                    width="100%",
                ),

                width="100%",
            ),

            spacing="5",
            padding_bottom="10",
        ),

        max_width="1200px",
    )


# =========================================================
# APP
# =========================================================

app = rx.App(

    head_components=[

        # MANIFEST
        rx.el.link(
            rel="manifest",
            href="manifest.json",
        ),

        # VIEWPORT
        rx.el.meta(
            name="viewport",
            content="width=device-width, initial-scale=1",
        ),

        # THEME
        rx.el.meta(
            name="theme-color",
            content="#2563eb",
        ),

        # IOS PWA
        rx.el.meta(
            name="apple-mobile-web-app-capable",
            content="yes",
        ),
        
        rx.el.meta(
            name="mobile-web-app-capable",
            content="yes",
        ),

        rx.el.meta(
            name="apple-mobile-web-app-status-bar-style",
            content="black-translucent",
        ),

        rx.el.meta(
            name="apple-mobile-web-app-title",
            content="AC FDD Hub",
        ),

        # PWA SCRIPT
        rx.el.script(src="pwa.js"),
    ]
)

app.add_page(
    index,
    on_load=State.fetch_all_data
)