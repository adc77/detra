#!/usr/bin/env python3
"""
Export Datadog Configurations for Challenge Submission

Exports all detra-related Datadog configurations to JSON files:
- Monitors
- Dashboards
- SLOs (if any)

Run: python scripts/export_datadog_configs.py
"""

import asyncio
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

from dotenv import load_dotenv

load_dotenv()


class DatadogExporter:
    """Export Datadog configurations for detra."""

    def __init__(self, output_dir: str = "datadog_exports"):
        """
        Initialize exporter.

        Args:
            output_dir: Directory to save exported configs.
        """
        # Setup Datadog API client
        self.configuration = Configuration()
        api_key = os.getenv("DD_API_KEY")
        app_key = os.getenv("DD_APP_KEY")
        site = os.getenv("DD_SITE", "datadoghq.com")

        if not api_key or not app_key:
            raise ValueError("DD_API_KEY and DD_APP_KEY must be set")

        self.configuration.api_key["apiKeyAuth"] = api_key
        self.configuration.api_key["appKeyAuth"] = app_key
        self.configuration.server_variables["site"] = site

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.exported_files = []

        print(f"✓ Datadog API configured (site: {site})")
        print(f"✓ Output directory: {self.output_dir}")

    def export_all(self):
        """Export all configurations."""
        print("\n" + "="*60)
        print("DATADOG CONFIGURATION EXPORT")
        print("="*60 + "\n")

        # Export monitors
        monitors = self.export_monitors()

        # Export dashboards
        dashboards = self.export_dashboards()

        # Export SLOs
        slos = self.export_slos()

        # Create summary
        self.create_summary(monitors, dashboards, slos)

        print("\n" + "="*60)
        print("EXPORT COMPLETE")
        print("="*60)
        print(f"\nExported {len(self.exported_files)} files to: {self.output_dir}")
        print("\nFiles:")
        for file in self.exported_files:
            print(f"  - {file}")
        print("\n" + "="*60 + "\n")

    def export_monitors(self) -> list:
        """Export all detra monitors."""
        print("Exporting monitors...")

        try:
            with ApiClient(self.configuration) as api_client:
                api = MonitorsApi(api_client)

                # Get all monitors
                monitors = api.list_monitors(
                    tags="source:detra",
                    name="detra",
                )

                # Convert to serializable format
                monitors_data = []
                for monitor in monitors:
                    monitor_dict = monitor.to_dict()
                    monitors_data.append(monitor_dict)

                # Save to file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"monitors_{timestamp}.json"
                filepath = self.output_dir / filename

                with open(filepath, 'w') as f:
                    json.dump(monitors_data, f, indent=2, default=str)

                self.exported_files.append(filename)
                print(f"  ✓ Exported {len(monitors_data)} monitors to {filename}")

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
                    d for d in dashboard_list.dashboards
                    if "detra" in d.title or "LLM Observability" in d.title
                ]

                dashboards_data = []

                for dashboard_summary in detra_dashboards:
                    # Get full dashboard details
                    dashboard = api.get_dashboard(dashboard_summary.id)
                    dashboard_dict = dashboard.to_dict()
                    dashboards_data.append(dashboard_dict)

                # Save to file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"dashboards_{timestamp}.json"
                filepath = self.output_dir / filename

                with open(filepath, 'w') as f:
                    json.dump(dashboards_data, f, indent=2, default=str)

                self.exported_files.append(filename)
                print(f"  ✓ Exported {len(dashboards_data)} dashboards to {filename}")

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

                # Get all SLOs
                slos_response = api.list_slos(tags="source:detra")

                slos_data = []
                if hasattr(slos_response, 'data') and slos_response.data:
                    for slo in slos_response.data:
                        slo_dict = slo.to_dict()
                        slos_data.append(slo_dict)

                if slos_data:
                    # Save to file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"slos_{timestamp}.json"
                    filepath = self.output_dir / filename

                    with open(filepath, 'w') as f:
                        json.dump(slos_data, f, indent=2, default=str)

                    self.exported_files.append(filename)
                    print(f"  ✓ Exported {len(slos_data)} SLOs to {filename}")
                else:
                    print(f"  ℹ️  No SLOs found with tag 'source:detra'")

                return slos_data

        except Exception as e:
            print(f"  ⚠️  Error exporting SLOs: {e}")
            return []

    def create_summary(self, monitors: list, dashboards: list, slos: list):
        """Create a summary file."""
        summary = {
            "export_date": datetime.now().isoformat(),
            "datadog_site": self.configuration.server_variables["site"],
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
            "slos": [
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "target_threshold": s.get("target_threshold"),
                }
                for s in slos
            ],
        }

        filename = "export_summary.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)

        self.exported_files.append(filename)
        print(f"  ✓ Created summary file: {filename}")

        # Also create a README
        readme_content = f"""# detra Datadog Configuration Export

Export Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Contents

This directory contains exported Datadog configurations for detra:

- **Monitors**: {len(monitors)} monitor(s)
- **Dashboards**: {len(dashboards)} dashboard(s)
- **SLOs**: {len(slos)} SLO(s)

## Files

{chr(10).join(f"- `{f}`" for f in self.exported_files)}

## Importing Configurations

To import these configurations into another Datadog org:

### Monitors
```python
from datadog_api_client.v1.api.monitors_api import MonitorsApi
import json

with open('monitors_*.json') as f:
    monitors = json.load(f)

for monitor in monitors:
    # Remove id and other auto-generated fields
    monitor.pop('id', None)
    monitor.pop('created', None)
    monitor.pop('modified', None)
    monitor.pop('creator', None)

    api.create_monitor(body=monitor)
```

### Dashboards
```python
from datadog_api_client.v1.api.dashboards_api import DashboardsApi
import json

with open('dashboards_*.json') as f:
    dashboards = json.load(f)

for dashboard in dashboards:
    dashboard.pop('id', None)
    dashboard.pop('created_at', None)
    dashboard.pop('modified_at', None)
    dashboard.pop('author_handle', None)

    api.create_dashboard(body=dashboard)
```

## detra Organization

Datadog Organization: `{os.getenv('DD_SITE', 'datadoghq.com')}`

## Detection Rules Summary

### Monitor 1: Adherence Score Warning
- **Type**: Metric Alert
- **Query**: `avg(last_5m):avg:detra.node.adherence_score{{*}} < 0.85`
- **Action**: Alert when LLM outputs fall below quality threshold

### Monitor 2: PII Detection
- **Type**: Event Alert
- **Query**: `sum(last_1m):sum:detra.security.pii_detected{{*}} > 0`
- **Action**: Critical alert on PII exposure in LLM outputs

### Monitor 3: High Latency
- **Type**: Metric Alert
- **Query**: `avg(last_5m):avg:detra.node.latency_ms{{*}} > 5000`
- **Action**: Warn when LLM response times exceed threshold

For full details, see the JSON configuration files.
"""

        readme_path = self.output_dir / "README.md"
        with open(readme_path, 'w') as f:
            f.write(readme_content)

        print(f"  ✓ Created README.md")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Export Datadog configurations for detra"
    )
    parser.add_argument(
        "--output-dir",
        default="datadog_exports",
        help="Output directory for exported configs",
    )

    args = parser.parse_args()

    # Check environment variables
    if not os.getenv("DD_API_KEY") or not os.getenv("DD_APP_KEY"):
        print("ERROR: DD_API_KEY and DD_APP_KEY must be set")
        print("\nSet them with:")
        print("  export DD_API_KEY=your_api_key")
        print("  export DD_APP_KEY=your_app_key")
        sys.exit(1)

    try:
        exporter = DatadogExporter(output_dir=args.output_dir)
        exporter.export_all()

        print("✅ Export completed successfully!")
        print(f"\nAdd these files to your GitHub repository:")
        print(f"  git add {args.output_dir}/")
        print(f"  git commit -m 'Add Datadog configuration exports'")
        print(f"  git push")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
