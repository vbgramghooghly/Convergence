import pandas as pd

def validate_import_dataframe(df, districts, departments, themes, blocks):
    errors = []
    required_cols = ['district_name', 'department_name', 'activity_description', 'convergence_type']
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")
            return errors  # can't proceed

    district_names = [d['district_name'] for d in districts]
    dept_names = [d['department_name'] for d in departments]
    theme_names = [t['theme_name'] for t in themes]
    block_names = [b['block_name'] for b in blocks]

    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel row number
        # Check district
        if pd.notna(row['district_name']) and row['district_name'] not in district_names:
            errors.append(f"Row {row_num}: Invalid district '{row['district_name']}'")
        # Check department
        if pd.notna(row['department_name']) and row['department_name'] not in dept_names:
            errors.append(f"Row {row_num}: Invalid department '{row['department_name']}'")
        # Check theme
        if pd.notna(row.get('thematic_category_name')) and row['thematic_category_name'] not in theme_names:
            errors.append(f"Row {row_num}: Invalid theme '{row['thematic_category_name']}'")
        # Check block
        if pd.notna(row.get('block_name')) and row['block_name'] not in block_names:
            errors.append(f"Row {row_num}: Invalid block '{row['block_name']}'")
        # Check numeric fields
        try:
            float(row.get('department_fund', 0))
            float(row.get('vbgramg_fund', 0))
            int(row.get('expected_persondays', 0))
        except:
            errors.append(f"Row {row_num}: Non-numeric value in fund or personday column.")
        # Check dates
        if pd.notna(row.get('target_start_date')) and not isinstance(row['target_start_date'], (pd.Timestamp,)):
            errors.append(f"Row {row_num}: Invalid start date.")
        if pd.notna(row.get('target_completion_date')) and not isinstance(row['target_completion_date'], (pd.Timestamp,)):
            errors.append(f"Row {row_num}: Invalid completion date.")
    return errors
