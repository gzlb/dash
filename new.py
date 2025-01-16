import streamlit as st
import pandas as pd
import uuid
from typing import List, Dict
from abc import ABC, abstractmethod


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
        # Generate a unique ID for this tab instance
        self.tab_id = str(uuid.uuid4())

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
        return [{"label": name, "value": name} for name in self._tab_classes.keys()]


# ------------------ DATA MANAGER ------------------ #
class DataManager:
    """
    Responsible for loading and storing multiple data files (CSV/XLSX).
    Now uses a generated UUID for each uploaded file instead of filename.
    """
    def __init__(self):
        # Map unique_id -> (df, optional filename)
        self.data_map = {}

    def load_data(self, file_obj) -> str:
        """
        Load the uploaded file (CSV/XLSX) into a DataFrame.
        We detect the file type by the extension in file_obj.name.
        We store the resulting DataFrame under a new UUID key.
        Returns the UUID key for reference.
        """
        unique_id = str(uuid.uuid4())
        filename = file_obj.name.lower()

        if filename.endswith(".xlsx"):
            try:
                df = pd.read_excel(file_obj)
            except ImportError:
                st.error("Could not import openpyxl. Please install it via `pip install openpyxl`.")
                return ""
        elif filename.endswith(".csv"):
            df = pd.read_csv(file_obj)
        else:
            st.warning(f"Unsupported file type: {file_obj.name}")
            return ""

        self.data_map[unique_id] = (df, file_obj.name)  # Store DataFrame + original name
        return unique_id

    def aggregate_data(self) -> pd.DataFrame:
        """
        Combine all dataframes into one master DataFrame.
        """
        if not self.data_map:
            return pd.DataFrame()

        dfs = [pair[0] for pair in self.data_map.values()]  # Extract DataFrame from (df, filename) tuple
        if len(dfs) == 1:
            return dfs[0]
        return pd.concat(dfs, ignore_index=True)

    def get_column_names(self) -> List[str]:
        df = self.aggregate_data()
        return list(df.columns)


# ------------------ EXAMPLE TABS ------------------ #
class UploadTab(Tab):
    """
    Lets the user upload one or more files, storing them in DataManager.
    Displays a preview of the combined data.
    """
    def render(self):
        st.subheader(f"Upload Tab (ID: {self.tab_id[:8]})")
        
        # Unique key for each UploadTab instance:
        widget_key = f"upload_files_{self.tab_id}"

        uploaded_files = st.file_uploader(
            "Upload CSV or XLSX files",
            type=["csv", "xlsx"],
            accept_multiple_files=True,
            key=widget_key
        )
        if uploaded_files:
            for uploaded_file in uploaded_files:
                uid = self.data_manager.load_data(uploaded_file)
                if uid:  # Successfully loaded
                    st.success(f"Uploaded: {uploaded_file.name} (UUID: {uid[:8]})")
        
        combined_df = self.data_manager.aggregate_data()
        if not combined_df.empty:
            st.write("Combined Data Preview:")
            st.dataframe(combined_df.head(20))
        else:
            st.write("No data uploaded yet.")


class PlotsTab(Tab):
    """
    Provides a dropdown of column names and creates a simple bar plot
    of value counts for the selected column.
    """
    def render(self):
        st.subheader(f"Plots Tab (ID: {self.tab_id[:8]})")
        df = self.data_manager.aggregate_data()

        if df.empty:
            st.warning("No data available. Please upload files first.")
            return

        col_list = self.data_manager.get_column_names()
        if not col_list:
            st.warning("No columns found in data.")
            return

        # Create a unique key for the selectbox:
        widget_key = f"plot_column_select_{self.tab_id}"
        selected_column = st.selectbox(
            "Select Column to Plot:",
            col_list,
            key=widget_key
        )
        if selected_column:
            counts = df[selected_column].value_counts()
            st.bar_chart(counts)


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

    def add_tab_to_sheet(self, sheet_index: int, tab: Tab):
        if sheet_index >= len(self.sheets):
            raise IndexError(f"Sheet index {sheet_index} does not exist.")
        self.sheets[sheet_index].append(tab)

    def get_sheet_count(self) -> int:
        return len(self.sheets)

    def get_tabs_in_sheet(self, sheet_index: int) -> List[Tab]:
        if 0 <= sheet_index < len(self.sheets):
            return self.sheets[sheet_index]
        return []

    def render_sheet(self, sheet_index: int):
        """
        Renders the selected sheet by creating a Streamlit tab layout
        for all Tab objects in that sheet.
        """
        if sheet_index < 0 or sheet_index >= len(self.sheets):
            st.write("No sheet selected.")
            return

        tabs = self.sheets[sheet_index]
        if not tabs:
            st.write("This sheet has no tabs.")
            return

        # Create labeled tabs, ensuring each is distinct
        # We'll display the tab's name plus a snippet of its unique ID.
        tab_titles = [f"Tab {i+1}: {type(t).__name__} [{t.tab_id[:8]}]" for i, t in enumerate(tabs)]
        st_tabs = st.tabs(tab_titles, key=f"sheet_{sheet_index}_tabs")

        # Render each Tab in its own st.tab container
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
        st.title("Dynamic Sheets Application (Streamlit + OOP)")

        self.init_session_state()

        # Pull the managers from session state
        data_manager: DataManager = st.session_state["data_manager"]
        tab_factory: TabFactory = st.session_state["tab_factory"]
        sheet_manager: SheetManager = st.session_state["sheet_manager"]

        # ------- MOVE SHEET CONTROLS TO LEFT SIDEBAR ------- #
        with st.sidebar:
            st.header("Sheets Manager")

            # Button: Add Sheet
            if st.button("Add Sheet", key="add_sheet_button"):
                sheet_manager.add_sheet()
                st.session_state["active_sheet_index"] = sheet_manager.get_sheet_count() - 1

            # Display existing sheets
            sheet_count = sheet_manager.get_sheet_count()
            if sheet_count > 0:
                st.write("Navigate Sheets:")
                for i in range(sheet_count):
                    if st.button(f"Sheet {i+1}", key=f"sheet_button_{i}"):
                        st.session_state["active_sheet_index"] = i

                active_sheet_index = st.session_state["active_sheet_index"]
                st.markdown(f"**Active Sheet**: {active_sheet_index + 1}")

                # Add a new Tab to the active sheet
                tab_options = tab_factory.get_tab_options()
                tab_type_values = [opt["value"] for opt in tab_options]

                selected_tab_type = st.selectbox(
                    "Select Tab Type",
                    options=tab_type_values,
                    key="select_tab_type"
                )

                if st.button("Add Tab to Sheet", key="add_tab_button"):
                    new_tab = tab_factory.create_tab(selected_tab_type, data_manager=data_manager)
                    sheet_manager.add_tab_to_sheet(active_sheet_index, new_tab)
                    # Rerun so the new tab is immediately visible
                    st.experimental_rerun()
            else:
                st.write("No sheets yet. Please add one above.")
        
        # ------- MAIN PAGE: ACTIVE SHEET DISPLAY ------- #
        if sheet_manager.get_sheet_count() > 0:
            active_sheet_index = st.session_state["active_sheet_index"]
            sheet_manager.render_sheet(active_sheet_index)
        else:
            st.write("No sheets to display. Create one from the sidebar.")

    def init_session_state(self):
        if "data_manager" not in st.session_state:
            st.session_state["data_manager"] = DataManager()
        if "tab_factory" not in st.session_state:
            st.session_state["tab_factory"] = TabFactory()
        if "sheet_manager" not in st.session_state:
            st.session_state["sheet_manager"] = SheetManager()
        if "active_sheet_index" not in st.session_state:
            st.session_state["active_sheet_index"] = 0


def main():
    app = StreamlitApp()
    app.run()


if __nam
