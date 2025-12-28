"""Dashboard builder utilities for creating custom dashboards."""

from typing import Any, Optional


class WidgetBuilder:
    """Builder for creating Datadog dashboard widgets."""

    @staticmethod
    def query_value(
        title: str,
        query: str,
        aggregator: str = "avg",
        precision: int = 2,
        unit: str = "",
        conditional_formats: Optional[list[dict]] = None,
        layout: Optional[dict[str, int]] = None,
    ) -> dict[str, Any]:
        """
        Create a query value widget.

        Args:
            title: Widget title.
            query: Metric query.
            aggregator: Aggregation function.
            precision: Decimal precision.
            unit: Custom unit.
            conditional_formats: Color thresholds.
            layout: Widget layout (x, y, width, height) for free layout dashboards.

        Returns:
            Widget definition.
        """
        widget = {
            "definition": {
                "title": title,
                "type": "query_value",
                "requests": [{"q": query}],
                "precision": precision,
            }
        }

        if unit:
            widget["definition"]["custom_unit"] = unit

        if conditional_formats:
            widget["definition"]["conditional_formats"] = conditional_formats

        if layout:
            widget["layout"] = layout

        return widget

    @staticmethod
    def timeseries(
        title: str,
        queries: list[dict[str, str]],
        markers: Optional[list[dict]] = None,
        yaxis: Optional[dict[str, str]] = None,
        layout: Optional[dict[str, int]] = None,
    ) -> dict[str, Any]:
        """
        Create a timeseries widget.

        Args:
            title: Widget title.
            queries: List of query definitions with q and display_type.
            markers: Optional threshold markers.
            yaxis: Y-axis configuration.
            layout: Widget layout (x, y, width, height) for free layout dashboards.

        Returns:
            Widget definition.
        """
        requests = []
        for q in queries:
            req = {"q": q["q"]}
            if "display_type" in q:
                req["display_type"] = q["display_type"]
            requests.append(req)

        widget = {
            "definition": {
                "title": title,
                "type": "timeseries",
                "requests": requests,
            }
        }

        if markers:
            widget["definition"]["markers"] = markers

        if yaxis:
            widget["definition"]["yaxis"] = yaxis

        if layout:
            widget["layout"] = layout

        return widget

    @staticmethod
    def toplist(
        title: str,
        query: str,
        palette: str = "dog_classic",
        layout: Optional[dict[str, int]] = None,
    ) -> dict[str, Any]:
        """
        Create a toplist widget.

        Args:
            title: Widget title.
            query: Metric query.
            palette: Color palette.
            layout: Widget layout (x, y, width, height) for free layout dashboards.

        Returns:
            Widget definition.
        """
        widget = {
            "definition": {
                "title": title,
                "type": "toplist",
                "requests": [{"q": query, "style": {"palette": palette}}],
            }
        }

        if layout:
            widget["layout"] = layout

        return widget

    @staticmethod
    def heatmap(
        title: str,
        query: str,
        layout: Optional[dict[str, int]] = None,
    ) -> dict[str, Any]:
        """
        Create a heatmap widget.

        Args:
            title: Widget title.
            query: Metric query.
            layout: Widget layout (x, y, width, height) for free layout dashboards.

        Returns:
            Widget definition.
        """
        widget = {
            "definition": {
                "title": title,
                "type": "heatmap",
                "requests": [{"q": query}],
            }
        }

        if layout:
            widget["layout"] = layout

        return widget

    @staticmethod
    def event_stream(
        title: str,
        query: str,
        size: str = "s",
        layout: Optional[dict[str, int]] = None,
    ) -> dict[str, Any]:
        """
        Create an event stream widget.

        Args:
            title: Widget title.
            query: Event query.
            size: Event size (s, l).
            layout: Widget layout (x, y, width, height) for free layout dashboards.

        Returns:
            Widget definition.
        """
        widget = {
            "definition": {
                "title": title,
                "type": "event_stream",
                "query": query,
                "event_size": size,
            }
        }

        if layout:
            widget["layout"] = layout

        return widget

    @staticmethod
    def group(
        title: str,
        widgets: list[dict[str, Any]],
        layout_type: str = "ordered",
    ) -> dict[str, Any]:
        """
        Create a group widget containing other widgets.

        Args:
            title: Group title.
            widgets: List of widgets to include.
            layout_type: Layout type (ordered, horizontal).

        Returns:
            Widget definition.
        """
        return {
            "definition": {
                "title": title,
                "type": "group",
                "layout_type": layout_type,
                "widgets": widgets,
            }
        }

    @staticmethod
    def monitor_summary(
        title: str,
        query: str,
        display_format: str = "countsAndList",
        layout: Optional[dict[str, int]] = None,
    ) -> dict[str, Any]:
        """
        Create a monitor summary widget.

        Args:
            title: Widget title.
            query: Monitor query.
            display_format: Display format.
            layout: Widget layout (x, y, width, height) for free layout dashboards.

        Returns:
            Widget definition.
        """
        widget = {
            "definition": {
                "title": title,
                "type": "manage_status",
                "query": query,
                "sort": "status,asc",
                "display_format": display_format,
            }
        }

        if layout:
            widget["layout"] = layout

        return widget

    @staticmethod
    def note(
        content: str,
        background_color: str = "white",
        font_size: str = "14",
        layout: Optional[dict[str, int]] = None,
    ) -> dict[str, Any]:
        """
        Create a note widget.

        Args:
            content: Markdown content.
            background_color: Background color.
            font_size: Font size.
            layout: Widget layout (x, y, width, height) for free layout dashboards.

        Returns:
            Widget definition.
        """
        widget = {
            "definition": {
                "type": "note",
                "content": content,
                "background_color": background_color,
                "font_size": font_size,
            }
        }

        if layout:
            widget["layout"] = layout

        return widget


class DashboardBuilder:
    """Builder for creating Datadog dashboards."""

    def __init__(self, title: str, description: str = ""):
        """
        Initialize the dashboard builder.

        Args:
            title: Dashboard title.
            description: Dashboard description.
        """
        self.title = title
        self.description = description
        self.widgets: list[dict[str, Any]] = []
        self.template_variables: list[dict[str, str]] = []
        self.layout_type = "free"

    def add_widget(self, widget: dict[str, Any]) -> "DashboardBuilder":
        """
        Add a widget to the dashboard.

        Args:
            widget: Widget definition.

        Returns:
            Self for chaining.
        """
        self.widgets.append(widget)
        return self

    def add_template_variable(
        self,
        name: str,
        prefix: str,
        default: str = "*",
    ) -> "DashboardBuilder":
        """
        Add a template variable.

        Args:
            name: Variable name.
            prefix: Tag prefix.
            default: Default value.

        Returns:
            Self for chaining.
        """
        self.template_variables.append({
            "name": name,
            "prefix": prefix,
            "default": default,
        })
        return self

    def set_layout(self, layout_type: str) -> "DashboardBuilder":
        """
        Set the layout type.

        Args:
            layout_type: Layout type (ordered, free).

        Returns:
            Self for chaining.
        """
        self.layout_type = layout_type
        return self

    def build(self) -> dict[str, Any]:
        """
        Build the dashboard definition.

        Returns:
            Complete dashboard JSON definition.
        """
        return {
            "title": self.title,
            "description": self.description,
            "widgets": self.widgets,
            "template_variables": self.template_variables,
            "layout_type": self.layout_type,
            "notify_list": [],
        }

    @classmethod
    def create_detra_dashboard(
        cls,
        app_name: str,
        env: str = "production",
    ) -> "DashboardBuilder":
        """
        Create a pre-configured detra dashboard builder.

        Args:
            app_name: Application name.
            env: Environment.

        Returns:
            Configured DashboardBuilder.
        """
        builder = cls(
            title=f"detra: {app_name} LLM Observability",
            description="End-to-end LLM observability dashboard",
        )

        # Add template variables
        builder.add_template_variable("node", "node")
        builder.add_template_variable("env", "env", default=env)

        # Add health overview widgets with layouts
        builder.add_widget(
            WidgetBuilder.query_value(
                "Adherence Score",
                "avg:detra.node.adherence_score{*}",
                conditional_formats=[
                    {"comparator": ">=", "value": 0.85, "palette": "white_on_green"},
                    {"comparator": ">=", "value": 0.70, "palette": "white_on_yellow"},
                    {"comparator": "<", "value": 0.70, "palette": "white_on_red"},
                ],
                layout={"x": 0, "y": 0, "width": 6, "height": 2},
            )
        )
        builder.add_widget(
            WidgetBuilder.query_value(
                "Flag Rate",
                "sum:detra.node.flagged{*}.as_count() / sum:detra.node.calls{*}.as_count() * 100",
                unit="%",
                precision=1,
                layout={"x": 6, "y": 0, "width": 6, "height": 2},
            )
        )

        # Add adherence trend
        builder.add_widget(
            WidgetBuilder.timeseries(
                "Adherence Over Time",
                [{"q": "avg:detra.node.adherence_score{*} by {node}", "display_type": "line"}],
                markers=[
                    {"value": "y = 0.85", "display_type": "warning dashed"},
                    {"value": "y = 0.70", "display_type": "error dashed"},
                ],
                yaxis={"min": "0", "max": "1"},
                layout={"x": 0, "y": 2, "width": 12, "height": 3},
            )
        )

        # Add flag analysis
        builder.add_widget(
            WidgetBuilder.toplist(
                "Flags by Category",
                "sum:detra.node.flagged{*} by {category}.as_count()",
                palette="warm",
                layout={"x": 0, "y": 5, "width": 6, "height": 3},
            )
        )

        # Add call volume
        builder.add_widget(
            WidgetBuilder.timeseries(
                "Call Volume",
                [{"q": "sum:detra.node.calls{*} by {node}.as_count()", "display_type": "bars"}],
                layout={"x": 6, "y": 5, "width": 6, "height": 3},
            )
        )

        return builder
