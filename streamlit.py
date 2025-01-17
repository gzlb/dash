import streamlit as st
import pandas as pd
import uuid
from typing import List, Dict
from abc import ABC, abstractmethod

# ------------------ FILTER WIDGET ------------------ #
class FilterWidget:
    """
    A standalone filter widget that:
      - Parses 'date' column to create 'year', 'quarter', 'month'
      - Lets user pick year(s), quarter(s), month(s)
      - Returns the filtered DataFrame
    """

    def __init__(self, df: pd.DataFrame, widget_key_prefix: str):
        """
        :param df: The unfiltered DataFrame
        :param widget_key_prefix: A unique string to differentiate widget keys
        """
        self.df = df.copy()
        self.widget_key_prefix = widget_key_prefix

    def render(self) -> pd.DataFrame:
        """
        Display the filter UI (year, quarter, month) and return filtered DataFrame.
        """
        # 1. Make sure we have a 'date' column
        if "date" not in self.df.columns:
            st.warning("No 'date' column found. Skipping date-based filters.")
            return self.df

        # 2. Convert 'date' to datetime, create year/quarter/month
        self.df["date"] = pd.to_datetime(self.df["date"], errors="coerce")
        self.df["year"] = self.df["date"].dt.year
        self.df["quarter"] = self.df["date"].dt.quarter
        self.df["month"] = self.df["date"].dt.month

        # 3. Year filter
        available_years = sorted(self.df["year"].dropna().unique())
        year_key = f"{self.widget_key_prefix}_year"
        selected_years = st.multiselect(
            "Filter by Years",
            options=available_years,
            key=year_key
        )
        df_filtered = self.df
        if selected_years:
            df_filtered = df_filtered[df_filtered["year"].isin(selected_years)]

        # 4. Quarter filter
        quarter_key = f"{self.widget_key_prefix}_quarter"
        selected_quarters = st.multiselect(
            "Filter by Quarters (1-4)",
            options=[1, 2, 3, 4],
            key=quarter_key
        )
        if selected_quarters:
            df_filtered = df_filtered[df_filtered["quarter"].isin(selected_quarters)]

        # 5. Month filter
        month_key = f"{self.widget_key_prefix}_month"
        # We only show the months that remain in df_filtered
        available_months = sorted(df_filtered["month"].dropna().unique())
        selected_months = st.multiselect(
            "Filter by Months (1-12)",
            options=available_months,
            key=month_key
        )
        if selected_months:
            df_filtered = df_filtered[df_filtered["month"].isin(selected_months)]

        st.write(f"Rows after filter: {len(df_filtered)}")
        return df_filtered


# ------------------ TAB BASE CLASS ------------------ #
class Tab(ABC):
    """
    Base class for all tabs. Each tab has:
      - A reference to a DataManager
      - A unique tab_id for unique widget keys
      - A render() method to display Streamlit UI elements
    """
    def __init__(self, data_manager=None):
        self.data_manager = data_manager
        self.tab_id = str(uuid.uuid4())  # unique ID to avoid widget key collisions

    @abstractmethod
    def render(self):
        """Renders the tab's UI with Streamlit calls."""
        pass


# ------------------ TAB FACTORY ------------------ #
class TabFactory:
    """
    Discovers all subclasses of Tab and lets you create them by name.
    """
    def __init__(self):
        self._tab_classes: Dict[str, Tab] = {}
        self.discover_tabs()

    def discover_tabs(self):
        for subclass in Tab.__subclasses__():
            tab_name = subclass.__name__
            self._tab_classes[tab_name] = subclass

    def create_tab(self, tab_name: str, data_manager=None) -> Tab:
        if tab_name not in self._tab_classes:
            raise ValueError(f"Tab '{tab_name}' is not registered.")
        return self._tab_classes[tab_name](data_manager=data_manager)

    def get_tab_options(self) -> List[dict]:
        """
        Returns a list of available Tab types, e.g.:
        [{"label": "UploadTab", "value": "UploadTab"}, {"label": "PlotTab", "value": "PlotTab"}, ...]
        """
        return [{"label": name, "value": name} for name in self._tab_classes.keys()]


# ------------------ DATA MANAGER ------------------ #
class DataManager:
    """
    Responsible for loading and storing multiple data files (CSV/XLSX).
    Uses a generated UUID for each uploaded file, not the filename.
    """
    def __init__(self):
        # unique_file_id -> (df, original_filename)
        self.data_map = {}

    def load_data(self, file_obj) -> str:
        """Load CSV or XLSX from a file into data_map under a new UUID."""
        unique_id = str(uuid.uuid4())
        filename = file_obj.name.lower()

        if filename.endswith(".xlsx"):
            try:
                df = pd.read_excel(file_obj)
            except ImportError:
                st.error("Could not import openpyxl. Install via `pip install openpyxl`.")
                return ""
        elif filename.endswith(".csv"):
            df = pd.read_csv(file_obj)
        else:
            st.warning(f"Unsupported file type: {file_obj.name}")
            return ""

        self.data_map[unique_id] = (df, file_obj.name)
        return unique_id

    def aggregate_data(self) -> pd.DataFrame:
        """
        Combine all stored DataFrames into one (unfiltered).
        """
        if not self.data_map:
            return pd.DataFrame()
        all_dfs = [pair[0] for pair in self.data_map.values()]
        if len(all_dfs) == 1:
            return all_dfs[0]
        return pd.concat(all_dfs, ignore_index=True)

    def get_column_names(self) -> List[str]:
        """
        Return column names of the aggregated (unfiltered) data.
        """
        df = self.aggregate_data()
        return list(df.columns)


# ------------------ UPLOAD TAB ------------------ #
class UploadTab(Tab):
    """
    Lets the user upload multiple CSV/XLSX files. Displays a sample of the combined data.
    """
    def render(self):
        st.subheader(f"Upload Tab (ID: {self.tab_id[:8]})")

        # Usually, we do not apply date filtering to an "Upload" tab, 
        # but if you wanted to, you could. For now, skip filter usage here.

        widget_key = f"upload_files_{self.tab_id}"
        uploaded_files = st.file_uploader(
            "Upload CSV or XLSX files",
            type=["csv", "xlsx"],
            accept_multiple_files=True,
            key=widget_key
        )
        if uploaded_files:
            for f in uploaded_files:
                uid = self.data_manager.load_data(f)
                if uid:
                    st.success(f"Uploaded: {f.name} (UUID: {uid[:8]})")

        # Show combined data
        df = self.data_manager.aggregate_data()
        if not df.empty:
            st.write("Combined Data Preview:")
            st.dataframe(df.head(20))
        else:
            st.write("No data uploaded yet.")


# ------------------ PLOT TAB ------------------ #
class PlotTab(Tab):
    """
    An example "plot" tab that uses FilterWidget to let the user pick 
    year/quarter/month, then displays a line chart of 'nominal' vs 'date'.
    """
    def render(self):
        st.subheader(f"Plot Tab (ID: {self.tab_id[:8]})")

        # 1. Get unfiltered data
        df = self.data_manager.aggregate_data()
        if df.empty:
            st.warning("No data available. Please upload files first.")
            return

        # 2. Use FilterWidget
        filter_key_prefix = f"plot_filter_{self.tab_id}"
        filter_widget = FilterWidget(df, filter_key_prefix)
        df_filtered = filter_widget.render()

        if df_filtered.empty:
            st.warning("No data left after filtering.")
            return

        # 3. Plot: 'nominal' vs. 'date'
        if "date" not in df_filtered.columns or "nominal" not in df_filtered.columns:
            st.error("Data must have 'date' and 'nominal' columns for plotting.")
            return

        df_filtered = df_filtered.dropna(subset=["date", "nominal"]).sort_values("date")
        st.line_chart(data=df_filtered, x="date", y="nominal")


# ------------------ AGGREGATION TAB ------------------ #
class AggregationTab(Tab):
    """
    Uses FilterWidget to let user pick year/quarter/month, 
    then groups data by user-chosen columns, summing 'nominal'.
    """
    def render(self):
        st.subheader(f"Aggregation Tab (ID: {self.tab_id[:8]})")

        # 1. Get unfiltered data
        df = self.data_manager.aggregate_data()
        if df.empty:
            st.warning("No data available or no data uploaded.")
            return

        # 2. Use FilterWidget
        filter_key_prefix = f"agg_filter_{self.tab_id}"
        filter_widget = FilterWidget(df, filter_key_prefix)
        df_filtered = filter_widget.render()

        if df_filtered.empty:
            st.warning("No data left after filtering.")
            return

        # 3. Grouping
        if "nominal" not in df_filtered.columns:
            st.error("No 'nominal' column found to aggregate.")
            return

        excluded_cols = {"nominal", "date", "year", "quarter", "month", "trade id"}
        groupable_cols = [c for c in df_filtered.columns if c.lower() not in excluded_cols]

        group_key = f"aggregation_groupby_{self.tab_id}"
        selected_group_cols = st.multiselect(
            "Group By Columns",
            options=groupable_cols,
            default=[],
            key=group_key
        )

        if selected_group_cols:
            grouped = df_filtered.groupby(selected_group_cols, dropna=False, as_index=False)["nominal"].sum()
            st.write(f"Aggregated by {selected_group_cols}, summing 'nominal':")
            st.dataframe(grouped)
        else:
            st.write("No grouping columns selected. Showing filtered data:")
            st.dataframe(df_filtered)


# ------------------ SHEET MANAGER ------------------ #
class SheetManager:
    """
    Manages multiple "sheets," each a list of tab objects.
    Allows adding new sheets and new tabs to each sheet.
    """
    def __init__(self):
        self.sheets = []

    def add_sheet(self):
        self.sheets.append([])

    def delete_sheet(self, index: int):
        if 0 <= index < len(self.sheets):
            self.sheets.pop(index)

    def add_tab_to_sheet(self, sheet_index: int, tab: Tab):
        if 0 <= sheet_index < len(self.sheets):
            self.sheets[sheet_index].append(tab)

    def delete_tab_from_sheet(self, sheet_index: int, tab_index: int):
        if 0 <= sheet_index < len(self.sheets):
            if 0 <= tab_index < len(self.sheets[sheet_index]):
                self.sheets[sheet_index].pop(tab_index)

    def get_sheet_count(self) -> int:
        return len(self.sheets)

    def get_tabs_in_sheet(self, sheet_index: int) -> List[Tab]:
        if 0 <= sheet_index < len(self.sheets):
            return self.sheets[sheet_index]
        return []

    def render_sheet(self, sheet_index: int):
        """
        Renders the tabs for the selected sheet in the main area.
        """
        if sheet_index < 0 or sheet_index >= len(self.sheets):
            st.write("No sheet selected.")
            return

        tabs = self.sheets[sheet_index]
        if not tabs:
            st.write("This sheet has no tabs.")
            return

        tab_titles = [
            f"{i+1}: {type(t).__name__} [{t.tab_id[:8]}]" 
            for i, t in enumerate(tabs)
        ]
        st_tabs = st.tabs(tab_titles)
        for i, tab_instance in enumerate(tabs):
            with st_tabs[i]:
                tab_instance.render()


# ------------------ STREAMLIT APP ------------------ #
class StreamlitApp:
    """
    Main application managing:
      - Session state init
      - DataManager, TabFactory, SheetManager
      - Rendering the overall UI structure
    """

    def __init__(self):
        pass

    def run(self):
        st.title("Standalone FilterWidget Demo (Streamlit + OOP)")

        self.init_session_state()

        sheet_manager: SheetManager = st.session_state["sheet_manager"]
        data_manager: DataManager = st.session_state["data_manager"]
        tab_factory: TabFactory = st.session_state["tab_factory"]

        # ----------------- LEFT SIDEBAR: SHEET CONTROL ----------------- #
        with st.sidebar:
            st.header("Sheet Management")

            # Create a sheet
            if st.button("Add New Sheet", key="add_sheet_btn"):
                sheet_manager.add_sheet()
                st.session_state["active_sheet_idx"] = sheet_manager.get_sheet_count() - 1

            # Show existing sheets & allow navigation or deletion
            sheet_count = sheet_manager.get_sheet_count()
            if sheet_count > 0:
                st.subheader("Existing Sheets:")
                for i in range(sheet_count):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        if st.button(f"Sheet {i+1}", key=f"sheet_nav_btn_{i}"):
                            st.session_state["active_sheet_idx"] = i
                    with col2:
                        # Delete this sheet
                        if st.button("X", key=f"sheet_delete_btn_{i}"):
                            sheet_manager.delete_sheet(i)
                            # Adjust active index if needed
                            if st.session_state["active_sheet_idx"] >= sheet_manager.get_sheet_count():
                                st.session_state["active_sheet_idx"] = sheet_manager.get_sheet_count() - 1
                            st.experimental_rerun()
                
                active_sheet_idx = st.session_state["active_sheet_idx"]
                if 0 <= active_sheet_idx < sheet_manager.get_sheet_count():
                    st.markdown(f"**Active Sheet**: {active_sheet_idx + 1}")
                else:
                    st.write("No valid sheet selected.")
            else:
                st.write("No sheets yet. Create one above.")

        # ----------------- MAIN AREA: TAB CONTROLS & TABS ----------------- #
        if sheet_manager.get_sheet_count() > 0:
            active_sheet_idx = st.session_state["active_sheet_idx"]
            st.write(f"### Active Sheet: {active_sheet_idx + 1}")

            # Add a new tab
            tab_options = tab_factory.get_tab_options()
            tab_types = [opt["value"] for opt in tab_options]
            selected_tab_type = st.selectbox(
                "Select Tab Type to Add",
                options=tab_types,
                key="select_tab_type_main"
            )
            if st.button("Add Tab", key="add_tab_btn_main"):
                new_tab = tab_factory.create_tab(selected_tab_type, data_manager=data_manager)
                sheet_manager.add_tab_to_sheet(active_sheet_idx, new_tab)
                st.experimental_rerun()

            # Delete a tab
            existing_tabs = sheet_manager.get_tabs_in_sheet(active_sheet_idx)
            if existing_tabs:
                delete_tab_options = [
                    f"{i+1}: {type(tab).__name__} [{tab.tab_id[:8]}]"
                    for i, tab in enumerate(existing_tabs)
                ]
                tab_to_delete = st.selectbox(
                    "Select Tab to Delete",
                    options=["<none>"] + delete_tab_options,
                    key="delete_tab_select"
                )
                if st.button("Delete Tab", key="delete_tab_btn"):
                    if tab_to_delete != "<none>":
                        # Figure out which index was chosen
                        delete_index = delete_tab_options.index(tab_to_delete)
                        sheet_manager.delete_tab_from_sheet(active_sheet_idx, delete_index)
                        st.experimental_rerun()

            st.markdown("---")

            # Render the tabs for the active sheet
            sheet_manager.render_sheet(active_sheet_idx)
        else:
            st.write("No sheets to display. Please create one in the sidebar.")

    def init_session_state(self):
        if "data_manager" not in st.session_state:
            st.session_state["data_manager"] = DataManager()
        if "tab_factory" not in st.session_state:
            st.session_state["tab_factory"] = TabFactory()
        if "sheet_manager" not in st.session_state:
            st.session_state["sheet_manager"] = SheetManager()
        if "active_sheet_idx" not in st.session_state:
            st.session_state["active_sheet_idx"] = 0


def main():
    app = StreamlitApp()
    app.run()


if __name__ == "__main__":
    main()
