import streamlit as st
import pandas as pd
import base64
import io
from typing import List, Dict
from abc import ABC, abstractmethod

# ------------------ TAB BASE CLASS ------------------ #
class Tab(ABC):
    """
    Base class for all tabs. Each tab has:
      - A reference to a DataManager (optional).
      - A render() method to display Streamlit UI elements.
    """
    def __init__(self, data_manager=None):
        self.data_manager = data_manager

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
    Provides methods to aggregate and retrieve column names.
    """
    def __init__(self):
        self.dataframes = {}

    def load_xlsx(self, file_obj, filename: str) -> pd.DataFrame:
        try:
            df = pd.read_excel(file_obj)
            self.dataframes[filename] = df
            return df
        except ImportError:
            st.error("Could not import openpyxl. Please install it via `pip install openpyxl`.")
            return pd.DataFrame()

    def load_csv(self, file_obj, filename: str) -> pd.DataFrame:
        df = pd.read_csv(file_obj)
        self.dataframes[filename] = df
        return df

    def load_data(self, file_obj, filename: str) -> pd.DataFrame:
        if filename.endswith(".xlsx"):
            return self.load_xlsx(file_obj, filename)
        elif filename.endswith(".csv"):
            return self.load_csv(file_obj, filename)
        else:
            raise NotImplementedError(f"File type for {filename} not supported.")

    def aggregate_data(self) -> pd.DataFrame:
        if len(self.dataframes) == 0:
            return pd.DataFrame()
        if len(self.dataframes) == 1:
            return next(iter(self.dataframes.values()))
        return pd.concat(self.dataframes.values(), ignore_index=True)

    def get_column_names(self) -> List[str]:
        df = self.aggregate_data()
        return list(df.columns)


# ------------------ EXAMPLE TABS ------------------ #
class UploadTab(Tab):
    """
    Lets the user upload one or more files. Displays a preview of the combined data.
    """
    def render(self):
        st.subheader("Upload Tab")

        uploaded_files = st.file_uploader(
            "Upload CSV or XLSX files",
            type=["csv", "xlsx"],
            accept_multiple_files=True,
            key="upload_files"
        )
        if uploaded_files:
            for uploaded_file in uploaded_files:
                self.data_manager.load_data(uploaded_file, uploaded_file.name)
            st.success("Files uploaded successfully.")

        # Show a snippet of combined data
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
        st.subheader("Plots Tab")
        df = self.data_manager.aggregate_data()

        if df.empty:
            st.warning("No data available. Please upload files first.")
            return

        col_list = self.data_manager.get_column_names()
        if not col_list:
            st.warning("No columns found in data.")
            return

        selected_column = st.selectbox(
            "Select Column to Plot:",
            col_list,
            key="plot_column_select"
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
        if sheet_index < 0 or sheet_index >= len(self.sheets):
            return []
        return self.sheets[sheet_index]

    def render_sheet(self, sheet_index: int):
        """
        Renders the selected sheet by calling render() on each tab,
        placing them in Streamlit's tab layout.
        """
        if sheet_index < 0 or sheet_index >= len(self.sheets):
            st.write("No sheet selected.")
            return

        tabs = self.sheets[sheet_index]
        if not tabs:
            st.write("This sheet has no tabs.")
            return

        tab_titles = [f"Tab {i+1}: {type(t).__name__}" for i, t in enumerate(tabs)]
        st_tabs = st.tabs(tab_titles, key=f"sheet_{sheet_index}_tabs")

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
                # Make the newly created sheet active
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
                    st.experimental_rerun()
            else:
                st.write("No sheets yet. Please add one above.")
        
        # ------- MAIN PAGE: ACTIVE SHEET DISPLAY ------- #
        # Only render if there's at least one sheet
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

if __name__ == "__main__":
    main()
