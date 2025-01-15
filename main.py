from abc import ABC, abstractmethod
import dash
from dash import dcc, html, Input, Output, State, dash_table, Dash
import pandas as pd
import base64
import io
from typing import List, Type

# Base Tab Interface
class Tab(ABC):
    @abstractmethod
    def create_tab(self) -> html.Div:
        """Creates a tab in the UI."""
        pass

    @abstractmethod
    def register_callbacks(self, app: Dash):
        """Registers all callbacks for the tab."""
        pass

# Factory for Creating Tabs
class TabFactory:
    def __init__(self):
        self._tab_classes = {}

    def discover_tabs(self):
        """Dynamically discovers all subclasses of Tab and registers them."""
        for subclass in Tab.__subclasses__():
            tab_name = subclass.__name__
            self._tab_classes[tab_name] = subclass

    def create_tab(self, tab_name: str, *args, **kwargs) -> Tab:
        """Instantiates and returns a tab by name."""
        if tab_name not in self._tab_classes:
            raise ValueError(f"Tab '{tab_name}' is not registered.")
        return self._tab_classes[tab_name](*args, **kwargs)

    def get_tab_options(self) -> List[dict]:
        """Returns a list of available tab options for the dropdown."""
        return [{"label": name, "value": name} for name in self._tab_classes.keys()]

# DataManager for handling multiple data sources/formats
class DataManager:
    def __init__(self):
        self.dataframes = {}

    def load_xlsx(self, content: str, filename: str) -> pd.DataFrame:
        content_type, content_string = content.split(',')
        decoded = base64.b64decode(content_string)
        df = pd.read_excel(io.BytesIO(decoded))
        self.dataframes[filename] = df
        return df

    def load_csv(self, content: str, filename: str) -> pd.DataFrame:
        content_type, content_string = content.split(',')
        decoded = base64.b64decode(content_string)
        df = pd.read_csv(io.BytesIO(decoded))
        self.dataframes[filename] = df
        return df

    def load_data(self, content: str, filename: str, filetype: str = "xlsx") -> pd.DataFrame:
        if filetype == "xlsx":
            return self.load_xlsx(content, filename)
        elif filetype == "csv":
            return self.load_csv(content, filename)
        else:
            raise NotImplementedError(f"Filetype {filetype} not supported yet.")

    def aggregate_data(self) -> pd.DataFrame:
        if len(self.dataframes) > 1:
            return pd.concat(self.dataframes.values(), ignore_index=True)
        return next(iter(self.dataframes.values()))

    def get_column_names(self) -> List[str]:
        if self.dataframes:
            return list(self.aggregate_data().columns)
        return []

# Example Tabs
class UploadTab(Tab):
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def create_tab(self) -> html.Div:
        return html.Div(
            [
                dcc.Upload(
                    id="upload-data",
                    children=html.Button("Drag and Drop or Select Files"),
                    multiple=True,
                ),
                html.Div(id="upload-output"),
            ]
        )

    def register_callbacks(self, app: dash.Dash):
        @app.callback(
            Output("upload-output", "children"),
            Input("upload-data", "contents"),
            State("upload-data", "filename"),
        )
        def handle_upload(contents_list, filenames):
            if contents_list:
                for contents, filename in zip(contents_list, filenames):
                    filetype = "xlsx" if filename.endswith(".xlsx") else "csv"
                    self.data_manager.load_data(contents, filename, filetype)
                combined_df = self.data_manager.aggregate_data()
                return dash_table.DataTable(
                    data=combined_df.to_dict("records"),
                    page_size=10,
                )
            return html.Div("No files uploaded")

class PlotsTab(Tab):
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def create_tab(self) -> html.Div:
        return html.Div(
            [
                dcc.Dropdown(
                    id="plot-column",
                    placeholder="Select column to plot",
                    style={
                        "font-size": "14px",
                        "padding": "5px",
                        "color": "#333",
                        "background-color": "#fff",
                        "border": "1px solid #ccc",
                        "border-radius": "5px",
                    },
                ),
                dcc.Graph(id="data-plot"),
            ]
        )

    def register_callbacks(self, app: dash.Dash):
        @app.callback(
            Output("data-plot", "figure"),
            Input("plot-column", "value"),
        )
        def create_plot(plot_column):
            if plot_column:
                df = self.data_manager.aggregate_data()
                return {
                    "data": [
                        {
                            "x": df[plot_column],
                            "y": df[plot_column].value_counts(),
                            "type": "bar",
                        }
                    ],
                    "layout": {"title": f"Bar Plot for {plot_column}"},
                }
            return {}

# Sheet Management with Dynamic Tabs
class SheetManager:
    def __init__(self):
        self.sheets = []  # Use a list to allow non-unique sheet identifiers

    def add_sheet(self):
        self.sheets.append([])  # Each sheet starts as an empty list of tabs

    def add_tab_to_sheet(self, sheet_index: int, tab: Tab):
        if sheet_index >= len(self.sheets):
            raise IndexError(f"Sheet index {sheet_index} does not exist.")
        self.sheets[sheet_index].append(tab)

    def get_sheet_layout(self, sheet_index: int, tab_factory):
        if sheet_index >= len(self.sheets):
            raise IndexError(f"Sheet index {sheet_index} does not exist.")

        tabs = self.sheets[sheet_index]
        return html.Div(
            [
                *[tab.create_tab() for tab in tabs],
                html.Div(
                    [
                        dcc.Dropdown(
                            id={"type": "tab-type-dropdown", "index": sheet_index},
                            options=tab_factory.get_tab_options(),
                            placeholder="Select Tab Type",
                            style={
                                "font-size": "14px",
                                "padding": "5px",
                                "color": "#333",
                                "background-color": "#fff",
                                "border": "1px solid #ccc",
                                "border-radius": "5px",
                            },
                        ),
                        html.Button(
                            "Add Tab", id={"type": "add-tab-button", "index": sheet_index},
                            style={"float": "right"},
                        ),
                    ],
                    style={"margin-top": "10px", "display": "flex", "justify-content": "space-between"},
                ),
            ]
        )

# Main App
class DashApp:
    def __init__(self):
        self.app = Dash(__name__, suppress_callback_exceptions=True)
        self.data_manager = DataManager()
        self.tab_factory = TabFactory()
        self.sheet_manager = SheetManager()
        self.active_sheet = 0  # Tracks the currently active sheet

        # Discover and register tabs dynamically
        self.tab_factory.discover_tabs()

        self.register_callbacks()

    def create_layout(self):
        self.app.layout = html.Div(
            [
                html.Div(
                    [
                        html.H1("Dynamic Sheets Application", style={"text-align": "center", "margin-bottom": "20px"}),
                        html.Div(
                            html.Button("Add Sheet", id="add-sheet-button", style={"float": "right"}),
                            style={"display": "flex", "justify-content": "space-between", "align-items": "center"},
                        ),
                        html.Div(
                            id="sheet-navigation",
                            style={"display": "flex", "gap": "10px", "margin-top": "20px"},
                        ),
                    ],
                    style={"margin-bottom": "20px"},
                ),
                html.Div(id="active-sheet-layout", style={"margin-top": "20px"}),
            ]
        )

    def register_callbacks(self):
        @self.app.callback(
            [
                Output("sheet-navigation", "children"),
                Output("active-sheet-layout", "children"),
            ],
            [
                Input("add-sheet-button", "n_clicks"),
                Input({"type": "sheet-button", "index": dash.ALL}, "n_clicks"),
                Input({"type": "add-tab-button", "index": dash.ALL}, "n_clicks"),
            ],
            [
                State({"type": "tab-type-dropdown", "index": dash.ALL}, "value"),
            ],
            prevent_initial_call=True,
        )
        def update_layout(n_clicks_add_sheet, n_clicks_sheet, n_clicks_add_tab, tab_type_values):
            ctx = dash.callback_context
            if not ctx.triggered:
                return [], html.Div()

            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

            # Handle adding a new sheet
            if triggered_id == "add-sheet-button":
                self.sheet_manager.add_sheet()
                self.active_sheet = len(self.sheet_manager.sheets) - 1

            # Handle sheet navigation
            elif "sheet-button" in triggered_id:
                triggered_id = eval(triggered_id)
                self.active_sheet = triggered_id["index"]

            # Handle adding a tab to the active sheet
            elif "add-tab-button" in triggered_id:
                triggered_id = eval(triggered_id)
                sheet_index = triggered_id["index"]
                tab_type = tab_type_values[0]
                if tab_type:
                    tab = self.tab_factory.create_tab(tab_type, self.data_manager)
                    self.sheet_manager.add_tab_to_sheet(sheet_index, tab)

            # Generate sheet navigation buttons
            sheet_buttons = [
                html.Button(
                    f"Sheet {i + 1}",
                    id={"type": "sheet-button", "index": i},
                    style={"padding": "10px", "background-color": "#f0f0f0"},
                )
                for i in range(len(self.sheet_manager.sheets))
            ]

            # Generate the layout for the active sheet
            active_sheet_layout = self.sheet_manager.get_sheet_layout(self.active_sheet, self.tab_factory)

            return sheet_buttons, active_sheet_layout

    def run(self):
        self.create_layout()
        self.app.run_server(debug=True)

if __name__ == "__main__":
    app = DashApp()
    app.run()





