import io
import pandas as pd
from openpyxl.utils import get_column_letter
from typing import Dict, Optional, List, Any, Union

# -----------------------------------------------------------------
# CORE EXPORT – safe, auto‑fitted, no fancy imports
# -----------------------------------------------------------------

def dataframe_to_excel(
    df: pd.DataFrame,
    sheet_name: str = "Sheet1",
    **kwargs  # Accept any extra arguments (title, freeze_panes, etc.) for compatibility
) -> bytes:
    """
    Convert a pandas DataFrame to an Excel binary stream with auto‑fitted columns.

    This is the safe, minimal version. It ignores advanced styling parameters
    to guarantee compatibility with all openpyxl versions.

    Parameters
    ----------
    df : pd.DataFrame
        The data to export.
    sheet_name : str, default "Sheet1"
        Name of the worksheet.

    Returns
    -------
    bytes
        Excel file content, ready for st.download_button.
    """
    # 1. Handle empty DataFrames gracefully
    if df is None or df.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame().to_excel(writer, index=False, sheet_name=sheet_name)
        return output.getvalue()

    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Write the data without the default pandas index
            df.to_excel(writer, index=False, sheet_name=sheet_name)

            # Auto‑fit column widths for a clean look
            worksheet = writer.sheets[sheet_name]
            for column in df.columns:
                # Calculate max length of data in this column (including header)
                max_len = max(
                    df[column].astype(str).map(len).max(),  # longest data cell
                    len(str(column))                         # header length
                )
                # Cap width to avoid breaking layout (50 characters is safe)
                max_len = min(max_len, 50)
                # Apply width (add 2 extra spaces for visual padding)
                col_idx = df.columns.get_loc(column) + 1
                worksheet.column_dimensions[get_column_letter(col_idx)].width = max_len + 2

        return output.getvalue()

    except Exception:
        # 2. Absolute fallback: try to write the most basic Excel file
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name=sheet_name)
            return output.getvalue()
        except:
            # Ultimate safety – return empty bytes to prevent application crash
            return b''


# -----------------------------------------------------------------
# EXTENDED FUNCTIONS (all using the safe core)
# -----------------------------------------------------------------

def export_dataframe(df: pd.DataFrame, **kwargs) -> bytes:
    """Alias for dataframe_to_excel."""
    return dataframe_to_excel(df, **kwargs)


def export_multi_sheet_workbook(
    dataframes: Dict[str, pd.DataFrame],
    title_per_sheet: Optional[Dict[str, str]] = None,
    **default_style_kwargs
) -> bytes:
    """
    Export multiple DataFrames into a single workbook, each on its own sheet.

    Parameters
    ----------
    dataframes : dict
        Mapping of sheet name -> DataFrame.
    title_per_sheet : dict, optional
        Ignored in this simple version (kept for compatibility).
    **default_style_kwargs
        Ignored (kept for compatibility).

    Returns
    -------
    bytes
        Excel file content.
    """
    if not dataframes:
        return dataframe_to_excel(pd.DataFrame())

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in dataframes.items():
            # Clean sheet name (remove invalid characters, max 31 chars)
            import re
            safe_name = re.sub(r'[\[\]\:\*\?\/\\]', '_', str(sheet_name))[:31] or "Sheet"
            # Write the DataFrame (without index)
            df.to_excel(writer, index=False, sheet_name=safe_name)

            # Auto‑fit columns for each sheet
            worksheet = writer.sheets[safe_name]
            for column in df.columns:
                max_len = max(
                    df[column].astype(str).map(len).max() if not df[column].empty else 0,
                    len(str(column))
                )
                max_len = min(max_len, 50)
                col_idx = df.columns.get_loc(column) + 1
                worksheet.column_dimensions[get_column_letter(col_idx)].width = max_len + 2

        # If no sheets were added (should not happen), create an empty one
        if not writer.book.sheetnames:
            writer.book.create_sheet("Empty")

    output.seek(0)
    return output.getvalue()


def export_with_summary(
    df: pd.DataFrame,
    summary_stats: Optional[Dict[str, Any]] = None,
    summary_sheet_name: str = "Summary",
    **kwargs
) -> bytes:
    """
    Export a DataFrame with an additional summary sheet.
    This simple version computes basic stats if none are provided.
    """
    if summary_stats is None:
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            summary_data = {
                'Count': df[numeric_cols].count(),
                'Mean': df[numeric_cols].mean(),
                'Std': df[numeric_cols].std(),
                'Min': df[numeric_cols].min(),
                'Max': df[numeric_cols].max()
            }
            summary_df = pd.DataFrame(summary_data).T.reset_index().rename(columns={'index': 'Metric'})
        else:
            summary_df = pd.DataFrame({'Note': ['No numeric columns to summarise']})
    else:
        summary_df = pd.DataFrame(summary_stats)

    sheets = {kwargs.get('sheet_name', 'Data'): df, summary_sheet_name: summary_df}
    return export_multi_sheet_workbook(sheets)


def export_with_totals(
    df: pd.DataFrame,
    total_row_label: str = "Total",
    total_columns: Optional[List[str]] = None,
    **kwargs
) -> bytes:
    """Export a DataFrame with a total row appended."""
    df_totals = df.copy()
    numeric_cols = total_columns if total_columns else df.select_dtypes(include=['number']).columns.tolist()
    total_row = {col: '' for col in df.columns}
    total_row[df.columns[0]] = total_row_label
    for col in numeric_cols:
        total_row[col] = df[col].sum()
    df_totals = pd.concat([df_totals, pd.DataFrame([total_row])], ignore_index=True)
    return dataframe_to_excel(df_totals, **kwargs)


def export_with_formulas(
    df: pd.DataFrame,
    formula_columns: Dict[str, str],
    **kwargs
) -> bytes:
    """
    Export a DataFrame with additional columns containing Excel formulas.
    Note: This simple version writes formulas as text (not evaluated) because
    openpyxl formula support is more complex. For safety, we add them as strings.
    """
    df_copy = df.copy()
    for col_name, formula in formula_columns.items():
        # Write the formula as a string (the user can manually convert in Excel)
        df_copy[col_name] = f"={formula}"
    return dataframe_to_excel(df_copy, **kwargs)


def export_with_charts(
    df: pd.DataFrame,
    chart_config: Dict[str, Any],
    **kwargs
) -> bytes:
    """
    Export with charts – this simple version ignores charts and just exports the data.
    Charts require more complex openpyxl operations; we skip them for safety.
    """
    # Just export the data; charts are not supported in this safe version
    return dataframe_to_excel(df, **kwargs)


def export_with_pivot_data(
    df: pd.DataFrame,
    pivot_config: Dict[str, Any],
    **kwargs
) -> bytes:
    """Export a DataFrame with a pivot table sheet (computed as static data)."""
    pivot_df = df.pivot_table(
        index=pivot_config.get('index', []),
        columns=pivot_config.get('columns', []),
        values=pivot_config.get('values', []),
        aggfunc=pivot_config.get('aggfunc', 'sum')
    ).reset_index()
    # Flatten multi‑index columns
    pivot_df.columns = ['_'.join(map(str, col)).strip('_') for col in pivot_df.columns]
    sheets = {
        kwargs.get('sheet_name', 'Data'): df,
        pivot_config.get('sheet_name', 'Pivot'): pivot_df
    }
    return export_multi_sheet_workbook(sheets)


def export_template(
    template_headers: List[str],
    sheet_name: str = "Template",
    **kwargs
) -> bytes:
    """Generate an empty Excel template with given headers."""
    df = pd.DataFrame(columns=template_headers)
    return dataframe_to_excel(df, sheet_name=sheet_name, **kwargs)


def import_excel(
    file_bytes: bytes,
    sheet_name: Optional[Union[str, int]] = None,
    **read_excel_kwargs
) -> Dict[str, pd.DataFrame]:
    """Import an Excel file and return a dict of DataFrames."""
    try:
        if sheet_name is not None:
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, **read_excel_kwargs)
            return {str(sheet_name): df}
        else:
            excel_data = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, **read_excel_kwargs)
            return {str(k): v for k, v in excel_data.items()}
    except Exception as e:
        return {'Error': pd.DataFrame({'Error': [str(e)]})}


def validate_excel(
    df: pd.DataFrame,
    required_columns: Optional[List[str]] = None,
    column_types: Optional[Dict[str, type]] = None,
    **kwargs
) -> tuple:
    """Validate a DataFrame against expected schema."""
    errors = []
    if required_columns:
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            errors.append(f"Missing required columns: {missing}")
    if column_types:
        for col, expected_type in column_types.items():
            if col in df.columns:
                actual_dtype = df[col].dtype
                if not pd.api.types.is_dtype_equal(actual_dtype, expected_type):
                    errors.append(f"Column '{col}' has dtype {actual_dtype}, expected {expected_type}")
            else:
                errors.append(f"Column '{col}' not found for type validation")
    if kwargs.get('not_null'):
        for col in kwargs['not_null']:
            if col in df.columns and df[col].isnull().any():
                errors.append(f"Column '{col}' contains null values")
    if kwargs.get('unique'):
        for col in kwargs['unique']:
            if col in df.columns and not df[col].is_unique:
                errors.append(f"Column '{col}' contains duplicate values")
    return len(errors) == 0, errors


def clean_excel(
    df: pd.DataFrame,
    strip_whitespace: bool = True,
    fillna: Optional[Dict[str, Any]] = None,
    dropna: bool = False,
    **kwargs
) -> pd.DataFrame:
    """Clean a DataFrame imported from Excel."""
    df_clean = df.copy()
    if strip_whitespace:
        string_cols = df_clean.select_dtypes(include=['object']).columns
        df_clean[string_cols] = df_clean[string_cols].apply(
            lambda x: x.str.strip() if x.dtype == 'object' else x
        )
    if fillna:
        for col, value in fillna.items():
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].fillna(value)
    if dropna:
        df_clean = df_clean.dropna()
    return df_clean


def compare_excel(
    file1_bytes: bytes,
    file2_bytes: bytes,
    sheet_name: Optional[Union[str, int]] = None,
    compare_kwargs: Optional[Dict[str, Any]] = None
) -> Dict[str, pd.DataFrame]:
    """Compare two Excel files and return differences."""
    df1_dict = import_excel(file1_bytes, sheet_name=sheet_name)
    df2_dict = import_excel(file2_bytes, sheet_name=sheet_name)
    result = {}
    compare_kwargs = compare_kwargs or {}
    for sheet, df1 in df1_dict.items():
        if sheet in df2_dict:
            df2 = df2_dict[sheet]
            try:
                diff = df1.compare(df2, **compare_kwargs)
                if not diff.empty:
                    result[sheet] = diff
            except Exception as e:
                result[sheet] = pd.DataFrame({'Error': [str(e)]})
        else:
            result[sheet] = pd.DataFrame({'Info': ['Sheet not found in second file']})
    return result


def merge_excel(
    file_bytes_list: List[bytes],
    sheet_name: Optional[str] = None,
    axis: int = 0,
    **kwargs
) -> bytes:
    """Merge multiple Excel files (or sheets) into a single workbook."""
    all_dfs = []
    for file_bytes in file_bytes_list:
        dfs = import_excel(file_bytes, sheet_name=sheet_name)
        if sheet_name is None:
            # Take the first sheet from each file
            df = list(dfs.values())[0]
        else:
            df = dfs.get(sheet_name)
            if df is None:
                continue
        all_dfs.append(df)
    if not all_dfs:
        return dataframe_to_excel(pd.DataFrame())
    merged_df = pd.concat(all_dfs, axis=axis, **kwargs)
    return dataframe_to_excel(merged_df, sheet_name="Merged")
