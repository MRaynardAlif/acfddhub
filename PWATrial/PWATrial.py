import os
import reflex as rx
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Force dotenv to look in the root folder, not the PWATrial folder
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# =========================================================
# STATE
# =========================================================
import datetime

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
    timeseries_data: list[dict] = []
    selected_unit: str = "INV 0.5PK"
    is_loading: bool = False
    
    # Date Filtering Variables
    start_date: str = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    end_date: str = datetime.date.today().isoformat()

    def fetch_all_data(self):
        self.get_timeseries()

    def set_selected_unit(self, value: str):
        self.selected_unit = value
        self.get_timeseries()

    def change_start_date(self, date_str: str):
        self.start_date = date_str
        self.get_timeseries()

    def change_end_date(self, date_str: str):
        self.end_date = date_str
        self.get_timeseries()

    def get_timeseries(self):
        if not supabase:
            return
            
        self.is_loading = True
        try:
            res = (
                supabase
                .table("ac_timeseries_data")
                .select("*")
                .eq("Unit", self.selected_unit)
                .gte("Timestamp", f"{self.start_date} 00:00:00")
                .lte("Timestamp", f"{self.end_date} 23:59:59")
                .order("Timestamp")
                .execute()
            )
            
            cleaned_data = []
            for r in res.data:
                try:
                    cleaned_data.append(
                        {
                            "time": str(r["Timestamp"])[:16].replace("T", " "),
                            "Condition": str(r["Condition"] or "UNKNOWN"),
                            "Cycle": str(r["Cycle"] or "UNKNOWN"),
                            "Incident_Count": int(r["Incident_Count"] or 0),
                            "Wattage": float(r["Avg_Wattage"] or 0),
                            "Voltage": float(r["Avg_Voltage"] or 0),
                            "Supply_Temp": float(r["Avg_Supply"] or 0),
                            "Return_Temp": float(r["Avg_Return"] or 0),
                            "Indoor_Temp": float(r["Avg_Indoor"] or 0),
                            "Delta": float(r["Avg_Delta"] or 0),
                        }
                    )
                except Exception:
                    continue

            self.timeseries_data = cleaned_data
        except Exception as e:
            print(f"Fetch Error: {e}")
        finally:
            self.is_loading = False

    # ---------------------------------------------------------
    # COMPUTED VARIABLES (Insights & Summaries)
    # ---------------------------------------------------------
    
    @rx.var
    def automated_insights(self) -> list[dict]:
        """Analyzes the current data window to generate smart text insights"""
        if not self.timeseries_data:
            return [{"text": "No data available for this period to generate insights.", "color": "gray", "icon": "info"}]
            
        insights = []
        data_len = len(self.timeseries_data)
        
        # 1. Cooling Efficiency Insight (Delta)
        avg_delta = sum(r["Delta"] for r in self.timeseries_data) / data_len
        if avg_delta >= 8.0:
            insights.append({"text": f"Healthy Cooling: Average Delta is strong at {avg_delta:.1f}°C.", "color": "green", "icon": "check-circle"})
        elif avg_delta > 0:
            insights.append({"text": f"Degraded Cooling: Average Delta is weak ({avg_delta:.1f}°C). Check filter/refrigerant.", "color": "orange", "icon": "alert-triangle"})
        else:
            insights.append({"text": f"Critical Cooling Failure: Average Delta is {avg_delta:.1f}°C. Unit is blowing warm air.", "color": "red", "icon": "x-circle"})

        # 2. Incident/Anomaly Insight
        max_incident = max(r["Incident_Count"] for r in self.timeseries_data)
        if max_incident == 0:
            insights.append({"text": "Stable Operation: Zero fault incidents recorded in this timeframe.", "color": "green", "icon": "shield-check"})
        else:
            insights.append({"text": f"Anomalies Detected: Reached up to {max_incident} simultaneous incidents. Check maintenance logs.", "color": "red", "icon": "alert-octagon"})

        # 3. Power Draw Insight
        max_wattage = max(r["Wattage"] for r in self.timeseries_data)
        avg_wattage = sum(r["Wattage"] for r in self.timeseries_data) / data_len
        insights.append({"text": f"Power Usage: Average draw is {avg_wattage:.1f} W (Peak: {max_wattage:.1f} W).", "color": "blue", "icon": "zap"})
        
        return insights

    @rx.var
    def computed_summary(self) -> list[dict]:
        summary_dict = {}
        for row in self.timeseries_data:
            key = f"{row['Condition']} - {row['Cycle']}"
            if key not in summary_dict:
                summary_dict[key] = {
                    "Condition": row["Condition"], "Cycle": row["Cycle"],
                    "Incidents": row["Incident_Count"], "Total_Wattage": 0.0,
                    "Total_Delta": 0.0, "Count": 0
                }
            summary_dict[key]["Total_Wattage"] += row["Wattage"]
            summary_dict[key]["Total_Delta"] += row["Delta"]
            summary_dict[key]["Count"] += 1
            summary_dict[key]["Incidents"] = max(summary_dict[key]["Incidents"], row["Incident_Count"])

        result = []
        for agg in summary_dict.values():
            result.append({
                "Condition": agg["Condition"], "Cycle": agg["Cycle"],
                "Incident_Count": agg["Incidents"],
                "Avg_Wattage": round(agg["Total_Wattage"] / agg["Count"], 2),
                "Avg_Delta": round(agg["Total_Delta"] / agg["Count"], 2),
            })
        return sorted(result, key=lambda x: x["Avg_Wattage"], reverse=True)

    @rx.var
    def total_incidents(self) -> str:
        if not self.timeseries_data: return "0"
        return str(max(r.get("Incident_Count", 0) for r in self.timeseries_data))

# =========================================================
# COMPONENTS & PAGE
# =========================================================

def condition_badge(condition):
    color = rx.match(
        condition,
        ("NORMAL", "green"),
        ("ABNORMAL", "red"),
        ("MAINTENANCE 1", "orange"),
        ("MAINTENANCE 2", "orange"),
        ("TROUBLE 1", "ruby"),
        ("TROUBLE 2", "ruby"),
        ("TROUBLE 3", "ruby"),
        "gray"
    )
    return rx.badge(condition, color_scheme=color)

def kpi_card(label, value, icon, value_color="black"):
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon(tag=icon, size=18),
                rx.text(label, size="2", color="gray"),
            ),
            rx.heading(value, size="6", color=value_color),
            align_items="start",
        ),
        width="100%",
    )

def index():
    return rx.container(
        rx.vstack(
            # HEADER
            rx.hstack(
                rx.heading("AC FDD Hub", size="8", color_scheme="blue"),
                rx.spacer(),
                rx.cond(State.is_loading, rx.spinner(size="3")),
                width="100%", align_items="center", padding_y="4",
            ),

            # DATE & UNIT CONTROLS
            rx.card(
                rx.flex(
                    rx.vstack(
                        rx.text("Select Analysis Unit", font_weight="bold"),
                        rx.select(UNITS, value=State.selected_unit, on_change=State.set_selected_unit, width="100%"),
                        width="100%", flex="1",
                    ),
                    rx.vstack(
                        rx.text("Start Date", font_weight="bold"),
                        rx.input(type="date", value=State.start_date, on_change=State.change_start_date, width="100%"),
                        width="100%", flex="1",
                    ),
                    rx.vstack(
                        rx.text("End Date", font_weight="bold"),
                        rx.input(type="date", value=State.end_date, on_change=State.change_end_date, width="100%"),
                        width="100%", flex="1",
                    ),
                    direction=rx.breakpoints(initial="column", sm="row"), spacing="4", width="100%",
                ),
                width="100%",
            ),

            # KPI GRID
            rx.grid(
                kpi_card("Current Unit", State.selected_unit, "cpu"),
                kpi_card("Period Max Incidents", State.total_incidents, "alert-triangle"),
                kpi_card("Data Points Assessed", State.timeseries_data.length(), "database"),
                columns=rx.breakpoints(initial="1", sm="2", md="3"),
                spacing="4", width="100%",
            ),

            # NEW FIXED: AUTOMATED INSIGHTS PANEL
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="lightbulb", size=20, color="orange"),
                        rx.heading("Automated System Insights", size="4"),
                    ),
                    rx.divider(),
                    rx.vstack(
                        rx.foreach(
                            State.automated_insights,
                            lambda insight: rx.hstack(
                                # FIX: Use rx.match so Reflex sees literal strings for icon tags
                                rx.match(
                                    insight["color"],
                                    ("green", rx.icon(tag="check-circle", color="green", size=18)),
                                    ("orange", rx.icon(tag="alert-triangle", color="orange", size=18)),
                                    ("red", rx.icon(tag="x-circle", color="red", size=18)),
                                    # Default fallback icon
                                    rx.icon(tag="info", color=insight["color"], size=18)
                                ),
                                rx.text(insight["text"], font_weight="medium"),
                                align_items="center",
                            )
                        ),
                        spacing="3",
                        align_items="start",
                    ),
                    align_items="start",
                    width="100%",
                ),
                width="100%",
                variant="surface",
            ),

            # CHARTS
            rx.grid(
                rx.card(
                    rx.vstack(
                        rx.heading(f"Power Draw (Wattage)", size="4"),
                        rx.recharts.line_chart(
                            rx.recharts.line(data_key="Wattage", stroke="#3b82f6", dot=False),
                            rx.recharts.x_axis(data_key="time"), rx.recharts.y_axis(),
                            rx.recharts.graphing_tooltip(), data=State.timeseries_data, width="100%", height=300,
                        ),
                        width="100%",
                    ),
                    width="100%",
                ),
                rx.card(
                    rx.vstack(
                        rx.heading(f"Thermodynamics (Supply vs Return)", size="4"),
                        rx.recharts.line_chart(
                            rx.recharts.line(data_key="Supply_Temp", stroke="#3b82f6", dot=False, name="Supply Temp"),
                            rx.recharts.line(data_key="Return_Temp", stroke="#ef4444", dot=False, name="Return Temp"),
                            rx.recharts.line(data_key="Indoor_Temp", stroke="#10b981", dot=False, name="Room Temp"),
                            rx.recharts.x_axis(data_key="time"), rx.recharts.y_axis(),
                            rx.recharts.graphing_tooltip(), rx.recharts.legend(), data=State.timeseries_data, width="100%", height=300,
                        ),
                        width="100%",
                    ),
                    width="100%",
                ),
                columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%",
            ),

            # DIAGNOSTIC TABLE
            rx.card(
                rx.vstack(
                    rx.heading("Diagnostic Breakdown (Selected Period)", size="4"),
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Status"), rx.table.column_header_cell("Cycle"),
                                rx.table.column_header_cell("Max Incidents"), rx.table.column_header_cell("Avg Wattage"),
                                rx.table.column_header_cell("Avg Cooling Delta"),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                State.computed_summary,
                                lambda r: rx.table.row(
                                    rx.table.cell(condition_badge(r["Condition"])), rx.table.cell(r["Cycle"]),
                                    rx.table.cell(r["Incident_Count"]), rx.table.cell(f"{r['Avg_Wattage']} W"),
                                    rx.table.cell(f"{r['Avg_Delta']} °C"),
                                )
                            )
                        ),
                        width="100%",
                    ),
                    width="100%",
                ),
                width="100%",
            ),
            spacing="5", padding_bottom="10",
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