import streamlit as st
import pandas as pd
import io
from utils.db import get_supabase
from utils.validators import validate_import_dataframe
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def dataframe_to_excel(df, sheet_name="Sheet1"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()
    
def show():
    require_role('superadmin')
    st.title("📤 Import Convergence Data from Excel")
    st.markdown("Download the template, fill it, and upload here.")

    # Template download
    template_df = pd.DataFrame(columns=[
        "financial_year", "district_name", "block_name", "gram_panchayat",
        "department_name", "activity_description", "thematic_category_name",
        "vbgramg_permissible", "number_status", "annual_plan_scope",
        "desired_target", "convergence_type", "department_fund",
        "vbgramg_fund", "pia", "expected_persondays",
        "target_start_date", "target_completion_date", "remarks"
    ])
    template_io = io.BytesIO()
    with pd.ExcelWriter(template_io, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False, sheet_name="Template")
    st.download_button("📥 Download Template", template_io.getvalue(), "convergence_import_template.xlsx")

    uploaded_file = st.file_uploader("Choose Excel file", type=["xlsx", "xls"])
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            st.subheader("Preview of uploaded data")
            st.dataframe(df.head(10))

            # Validate
            supabase = get_supabase()
            districts = supabase.table("districts").select("id,district_name").execute().data
            depts = supabase.table("departments").select("id,department_name").execute().data
            themes = supabase.table("themes").select("id,theme_name").execute().data
            blocks = supabase.table("blocks").select("id,block_name").execute().data

            errors = validate_import_dataframe(df, districts, depts, themes, blocks)
            if errors:
                st.error("Validation errors found:")
                for err in errors:
                    st.write(f"🔴 {err}")
                st.stop()
            else:
                st.success("Validation passed! Click 'Confirm Import' to insert records.")

            if st.button("Confirm Import"):
                user = get_current_user()
                inserted = 0
                for idx, row in df.iterrows():
                    # Map names to IDs
                    dist_id = next(d['id'] for d in districts if d['district_name'] == row['district_name'])
                    dept_id = next(d['id'] for d in depts if d['department_name'] == row['department_name'])
                    theme_id = None
                    if pd.notna(row.get('thematic_category_name')):
                        theme_id = next(t['id'] for t in themes if t['theme_name'] == row['thematic_category_name'])
                    block_id = None
                    if pd.notna(row.get('block_name')):
                        block_match = [b for b in blocks if b['block_name'] == row['block_name']]
                        if block_match:
                            block_id = block_match[0]['id']
                    # Build record
                    record = {
                        "financial_year": row['financial_year'],
                        "district_id": dist_id,
                        "block_id": block_id,
                        "gram_panchayat": row.get('gram_panchayat'),
                        "department_id": dept_id,
                        "activity_description": row['activity_description'],
                        "thematic_category_id": theme_id,
                        "vbgramg_permissible": bool(row.get('vbgramg_permissible', False)),
                        "number_status": row.get('number_status'),
                        "annual_plan_scope": row.get('annual_plan_scope'),
                        "desired_target": row.get('desired_target', 0),
                        "convergence_type": row['convergence_type'],
                        "department_fund": row.get('department_fund', 0),
                        "vbgramg_fund": row.get('vbgramg_fund', 0),
                        "pia": row.get('pia'),
                        "expected_persondays": row.get('expected_persondays', 0),
                        "target_start_date": str(row['target_start_date']) if pd.notna(row.get('target_start_date')) else None,
                        "target_completion_date": str(row['target_completion_date']) if pd.notna(row.get('target_completion_date')) else None,
                        "current_status": "Planned",
                        "remarks": row.get('remarks'),
                        "created_by": user['id']
                    }
                    result = supabase.table("convergence_register").insert(record).execute()
                    if result.data:
                        log_action(user, "IMPORT", "convergence_register", result.data[0]['id'], new_vals=record)
                        inserted += 1
                st.success(f"Successfully imported {inserted} records.")
                st.rerun()
        except Exception as e:
            st.error(f"Error reading file: {e}")
