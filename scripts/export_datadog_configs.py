#!/usr/bin/env python3
"""
Export Datadog Configurations for Challenge Submission

Exports all detra-related Datadog configurations to JSON files:
- Monitors
- Dashboards
- SLOs (if any)

Run: python scripts/export_datadog_configs.py
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.dashboards_api import DashboardsApi
from datadog_api_client.v1.api.monitors_api import MonitorsApi
from datadog_api_client.v1.api.service_level_objectives_api import ServiceLevelObjectivesApi


def load_env_vars():
    """Load environment variables manually."""
    env = {}
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip()
    return env


env = load_env_vars()
DD_API_KEY = env.get("DD_API_KEY", os.getenv("DD_API_KEY"))
DD_APP_KEY = env.get("DD_APP_KEY", os.getenv("DD_APP_KEY"))
DD_SITE = env.get("DD_SITE", os.getenv("DD_SITE", "datadoghq.com"))

if not DD_API_KEY or not DD_APP_KEY:
    print("ERROR: DD_API_KEY and DD_APP_KEY must be set")
    print("\nSet them in .env file:")
    print("  DD_API_KEY=your_api_key")
    print("  DD_APP_KEY=your_app_key")
    print("  DD_SITE=datadoghq.com  # or us5.datadoghq.com, etc.")
    sys.exit(1)

configuration = Configuration()
configuration.api_key["apiKeyAuth"] = DD_API_KEY
configuration.api_key["appKeyAuth"] = DD_APP_KEY
configuration.server_variables["site"] = DD_SITE


class DatadogExporter:
    """Export Datadog configurations for detra."""

    def __init__(self, output_dir: str = "datadog_exports"):
        self.configuration = Configuration()
        self.configuration.api_key["apiKeyAuth"] = DD_API_KEY
        self.configuration.api_key["appKeyAuth"] = DD_APP_KEY
        self.configuration.server_variables["site"] = DD_SITE

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.exported_files = []

        print(f"✓ Datadog API configured (site: {DD_SITE})")
        print(f"✓ Output directory: {self.output_dir}")

    def export_all(self):
        """Export all configurations."""
        print("\n" + "=" * 60)
        print("DATADOG CONFIGURATION EXPORT")
        print("=" * 60 + "\n")

        # Export monitors
        monitors = self.export_monitors()

        # Export dashboards
        dashboards = self.export_dashboards()

        # Export SLOs
        slos = self.export_slos()

        # Create summary
        self.create_summary(monitors, dashboards, slos)

        print("\n" + "=" * 60)
        print("EXPORT COMPLETE")
        print("=" * 60)
        print(f"\nExported {len(self.exported_files)} files to: {self.output_dir}")
        print("\nFiles:")
        for file in self.exported_files:
            print(f"  - {file}")
        print("\n" + "=" * 60 + "\n")

    def export_monitors(self) -> list:
        """Export all detra monitors."""
        print("Exporting monitors...")

        try:
            with ApiClient(self.configuration) as api_client:
                api = MonitorsApi(api_client)

                # Get all monitors - without filters to find all
                monitors = api.list_monitors()

                # Filter for detra monitors
                detra_monitors = [m for m in monitors if "detra" in m.name.lower()]

                # Convert to serializable format
                monitors_data = []
                for monitor in detra_monitors:
                    monitors_data.append(monitor.to_dict())

                # Save to file
                if monitors_data:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"monitors_{timestamp}.json"
                    filepath = self.output_dir / filename

                    with open(filepath, "w") as f:
                        json.dump(monitors_data, f, indent=2, default=str)

                    self.exported_files.append(filename)
                    print(f"  ✓ Exported {len(monitors_data)} monitors to {filename}")
                else:
                    print(f"  ℹ️  No detra monitors found")

                return monitors_data

        except Exception as e:
            print(f"  ⚠️  Error exporting monitors: {e}")
            return []

    def export_dashboards(self) -> list:
        """Export all detra dashboards."""
        print("Exporting dashboards...")

        try:
            with ApiClient(self.configuration) as api_client:
                api = DashboardsApi(api_client)

                # List all dashboards
                dashboard_list = api.list_dashboards()

                # Filter detra dashboards
                detra_dashboards = [
                    d
                    for d in dashboard_list.dashboards
                    if "detra" in d.title.lower() or "llm" in d.title.lower()
                ]

                dashboards_data = []
                for dashboard in detra_dashboards:
                    # Get full dashboard details
                    dashboard_detail = api.get_dashboard(dashboard.id)
                    dashboards_data.append(dashboard_detail.to_dict())

                # Save to file
                if dashboards_data:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"dashboards_{timestamp}.json"
                    filepath = self.output_dir / filename

                    with open(filepath, "w") as f:
                        json.dump(dashboards_data, f, indent=2, default=str)

                    self.exported_files.append(filename)
                    print(f"  ✓ Exported {len(dashboards_data)} dashboards to {filename}")
                else:
                    print(f"  ℹ️  No detra dashboards found")

                return dashboards_data

        except Exception as e:
            print(f"  ⚠️  Error exporting dashboards: {e}")
            return []

    def export_slos(self) -> list:
        """Export all detra SLOs."""
        print("Exporting SLOs...")

        try:
            with ApiClient(self.configuration) as api_client:
                api = ServiceLevelObjectivesApi(api_client)

                # List all SLOs
                slos_response = api.list_slos()

                slos_data = []
                if hasattr(slos_response, "data") and slos_response.data:
                    slos_list = slos_response.data

                    # Filter for detra SLOs
                    detra_slos = [s for s in slos_list if s.name and "detra" in s.name.lower()]

                    for slo in detra_slos:
                        slos_data.append(slo.to_dict())

                # Save to file
                if slos_data:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"slos_{timestamp}.json"
                    filepath = self.output_dir / filename

                    with open(filepath, "w") as f:
                        json.dump(slos_data, f, indent=2, default=str)

                    self.exported_files.append(filename)
                    print(f"  ✓ Exported {len(slos_data)} SLOs to {filename}")
                else:
                    print(f"  ℹ️  No detra SLOs found")

                return slos_data

        except Exception as e:
            print(f"  ⚠️  Error exporting SLOs: {e}")
            return []

    def create_summary(self, monitors: list, dashboards: list, slos: list):
        """Create a summary file."""
        summary = {
            "export_date": datetime.now().isoformat(),
            "datadog_site": DD_SITE,
            "summary": {
                "monitors": len(monitors),
                "dashboards": len(dashboards),
                "slos": len(slos),
            },
            "monitors": [
                {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "type": m.get("type"),
                    "tags": m.get("tags", []),
                    "query": m.get("query"),
                }
                for m in monitors
            ],
            "dashboards": [
                {
                    "id": d.get("id"),
                    "title": d.get("title"),
                    "url": d.get("url"),
                }
                for d in dashboards
            ],
            "slos": slos,
        }

        filename = "export_summary.json"
        filepath = self.output_dir / filename

        with open(filepath, "w") as f:
            json.dump(summary, f, indent=2)

        self.exported_files.append(filename)
        print(f"  ✓ Created summary file: {filename}")


def main():
    parser = argparse.ArgumentParser(description="Export Datadog configurations for detra")
    parser.add_argument(
        "--output-dir",
        default="datadog_exports",
        help="Output directory for exported configs",
    )

    args = parser.parse_args()

    try:
        exporter = DatadogExporter(output_dir=args.output_dir)
        exporter.export_all()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
