import streamlit as st
import pandas as pd
import base64
import io
from abc import ABC, abstractmethod
from typing import List, Type

# -----------------------------------------------------------------------
#  DataManager: Handles all data loading and aggregation
# -----------------------------------------------------------------------
class DataManager:
    def __init__(self):
        self.dataframes = {}  # key=filename, value=pd.DataFrame
    
    def load_xlsx(self, file_bytes: bytes, filename: str) -> pd.DataFrame:
        df = pd.read_excel(io.BytesIO(file_bytes))
        self.dataframes[filename] = df
        return df

    def load_csv(self, file_bytes: bytes, filename: str) -> pd.DataFrame:
        df = pd.read_csv(io.BytesIO(file_bytes))
        self.dataframes[filename] = df
        return df

    def load_data(self, file_bytes: bytes, filename: str) -> pd.DataFrame:
        """Decide file type (XLSX or CSV) and load."""
        if filename.endswith(".xlsx"):
            return self.load_xlsx(file_bytes, filename)
        elif filename.endswith(".csv"):
            return self.load_csv(file_bytes, filename)
        else:
            raise NotImplementedError(f"Unsupported file extension in {filename}.")
    
    def aggregate_data(self) -> pd.DataFrame:
        if not self.dataframes:
            return pd.DataFrame()
        return pd.concat(self.dataframes.values(), ignore_index=True)

    def get_column_names(self) -> List[str]:
        df = self.aggregate_data()
        return list(df.columns) if not df.empty else []


# -----------------------------------------------------------------------
#  Base Tab Interface
# -----------------------------------------------------------------------
class Tab(ABC):
    @abstractmethod
    def render(self):
        """Render the UI for this tab using Streamlit calls."""
        pass


# -----------------------------------------------------------------------
#  Concrete Tab Implementations
# -----------------------------------------------------------------------
class UploadTab(Tab):
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def render(self):
        st.subheader("Upload Tab")
        uploaded_files = st.file_uploader(
            "Upload your files (XLSX or CSV)",
            accept_multiple_files=True
        )
        if uploaded_files:
            for file in uploaded_files:
                if file is not None:
                    # Read the entire file into memory
                    file_bytes = file.read()
                    self.data_manager.load_data(file_bytes, file.name)
            st.success("Files uploaded and loaded into DataManager.")

        # Display combined dataframe
        combined_df = self.data_manager.aggregate_data()
        if not combined_df.empty:
            st.write("Combined Data Preview:")
            st.dataframe(combined_df.head(50))


class PlotsTab(Tab):
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def render(self):
        st.subheader("Plots Tab")
        df = self.data_manager.aggregate_data()
        if df.empty:
            st.info("No data found. Please upload a file in the 'Upload Tab' first.")
            return
        
        columns = self.data_manager.get_column_names()
        if not columns:
            st.warning("No columns found in the data.")
            return

        # Select a column to plot
        plot_column = st.selectbox("Select column to plot:", options=columns)
        if plot_column:
            # For simplicity, let's do a simple bar chart of value counts
            counts = df[plot_column].value_counts().reset_index()
            counts.columns = [plot_column, "Count"]
            st.bar_chart(data=counts.set_index(plot_column))


# -----------------------------------------------------------------------
#  TabFactory: Dynamically discovers and creates Tab objects
# -----------------------------------------------------------------------
class TabFactory:
    def __init__(self):
        self._tab_classes = {}
        self.discover_tabs()

    def discover_tabs(self):
        """Register all current subclasses of Tab."""
        for subclass in Tab.__subclasses__():
            self._tab_classes[subclass.__name__] = subclass

    def create_tab(self, tab_name: str, data_manager: DataManager) -> Tab:
        """Create a tab object by name."""
        if tab_name not in self._tab_classes:
            raise ValueError(f"Tab '{tab_name}' is not registered.")
        return self._tab_classes[tab_name](data_manager)

    def get_tab_options(self) -> List[str]:
        """Returns a list of valid tab names."""
        return list(self._tab_classes.keys())


# -----------------------------------------------------------------------
#  SheetManager: Holds multiple "Sheets", each of which can contain Tabs
# -----------------------------------------------------------------------
class SheetManager:
    def __init__(self):
        # Each element of self.sheets is a list of tab names (strings) 
        # that exist in that sheet.
        self.sheets = []

    def add_sheet(self):
        """Create a new, empty sheet."""
        self.sheets.append([])

    def add_tab_to_sheet(self, sheet_index: int, tab_name: str):
        """Add a tab to an existing sheet by name."""
        if sheet_index < 0 or sheet_index >= len(self.sheets):
            raise IndexError(f"Sheet index {sheet_index} is out of range.")
        self.sheets[sheet_index].append(tab_name)

    def get_sheet_tabs(self, sheet_index: int) -> List[str]:
        """Return the list of tab names for the given sheet."""
        return self.sheets[sheet_index]


# -----------------------------------------------------------------------
#  Main Streamlit Application in an OOP Format
# -----------------------------------------------------------------------
class StreamlitApp:
    def __init__(self):
        # Initialize session state variables if they do not exist
        if "data_manager" not in st.session_state:
            st.session_state["data_manager"] = DataManager()
        if "tab_factory" not in st.session_state:
            st.session_state["tab_factory"] = TabFactory()
        if "sheet_manager" not in st.session_state:
            st.session_state["sheet_manager"] = SheetManager()
        if "active_sheet" not in st.session_state:
            st.session_state["active_sheet"] = 0

        self.data_manager: DataManager = st.session_state["data_manager"]
        self.tab_factory: TabFactory = st.session_state["tab_factory"]
        self.sheet_manager: SheetManager = st.session_state["sheet_manager"]

    def _set_active_sheet(self, sheet_index: int):
        st.session_state["active_sheet"] = sheet_index

    def run(self):
        st.title("Streamlit Dynamic Sheets & Tabs (OOP Edition)")
        self._render_sheet_controls()
        self._render_active_sheet()

    def _render_sheet_controls(self):
        # Create or navigate sheets
        if st.button("Add New Sheet"):
            self.sheet_manager.add_sheet()
            self._set_active_sheet(len(self.sheet_manager.sheets) - 1)

        # Navigation for existing sheets
        with st.container():
            st.markdown("### Navigate Sheets")
            for i, tabs in enumerate(self.sheet_manager.sheets):
                sheet_button_label = f"Sheet {i+1}"
                if st.button(sheet_button_label, key=f"sheet_button_{i}"):
                    self._set_active_sheet(i)

    def _render_active_sheet(self):
        active_sheet_idx = st.session_state["active_sheet"]
        sheets = self.sheet_manager.sheets
        
        if not sheets:
            st.write("No sheets yet. Click 'Add New Sheet' above to create one.")
            return

        # Safety check for index
        if active_sheet_idx < 0 or active_sheet_idx >= len(sheets):
            st.error("Active sheet index is invalid.")
            return
        
        st.subheader(f"Active Sheet: {active_sheet_idx + 1}")
        current_tabs = sheets[active_sheet_idx]

        # Add new tab to this sheet
        st.write("---")
        st.write("#### Add a Tab to This Sheet")
        available_tabs = self.tab_factory.get_tab_options()
        chosen_tab_type = st.selectbox("Choose Tab Type", available_tabs, key="tab_type_select")
        if st.button("Add Tab to Sheet"):
            self.sheet_manager.add_tab_to_sheet(active_sheet_idx, chosen_tab_type)
            st.experimental_rerun()

        st.write("---")
        st.write("#### Tabs in This Sheet")
        if not current_tabs:
            st.write("No tabs in this sheet yet.")
            return

        # Render each tab within Streamlit's built-in tab layout
        tab_labels = [f"{t}" for t in current_tabs]
        st_tabs = st.tabs(tab_labels)
        for tab_idx, tab_name in enumerate(current_tabs):
            with st_tabs[tab_idx]:
                # Create an instance of the tab from the factory
                tab_object = self.tab_factory.create_tab(tab_name, self.data_manager)
                tab_object.render()


# -----------------------------------------------------------------------
#  Entry point
# -----------------------------------------------------------------------
def main():
    app = StreamlitApp()
    app.run()

if __name__ == "__main__":
    main()
