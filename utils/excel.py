import pandas as pd
import io
from openpyxl.utils import get_column_letter

def dataframe_to_excel(df, sheet_name="Sheet1"):
    """
    Convert a pandas DataFrame to an Excel binary stream.
    Includes auto-fit columns for better modern spreadsheet readability.
    """
    # 1. Handle Empty DataFrames gracefully
    if df.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame().to_excel(writer, index=False, sheet_name=sheet_name)
        return output.getvalue()

    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Export the data without the default Pandas index
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            
            # 2. Auto-fit column widths for a modern, professional look
            worksheet = writer.sheets[sheet_name]
            for column in df:
                # Find the maximum length of the data in this column (including the header)
                column_length = max(
                    df[column].astype(str).map(len).max(),  # Max data length
                    len(str(column))                        # Header length
                )
                # Cap the width at 50 to prevent very long text from breaking the layout
                column_length = min(column_length, 50)
                
                # Get the column letter and apply the width (adding 2 extra spaces for padding)
                col_idx = df.columns.get_loc(column) + 1
                worksheet.column_dimensions[get_column_letter(col_idx)].width = column_length + 2
                
        return output.getvalue()
        
    except Exception as e:
        # 3. Robust Fallback: If anything fails (e.g., openpyxl formatting bug), 
        # it will fall back to exporting the basic Excel file anyway.
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name=sheet_name)
            return output.getvalue()
        except:
            # Absolute fail-safe, returns an empty bytes object to prevent crash
            return b''
