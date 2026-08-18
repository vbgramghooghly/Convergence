import streamlit as st
import pandas as pd
import io
import re
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.theme import apply_global_theme

# ---------- CONSTANTS ----------
DISTRICT_NAMES = {
    1: "Alipurduar", 2: "Bankura", 3: "Birbhum", 4: "Cooch Behar",
    5: "Dakshin Dinajpur", 6: "Darjeeling", 7: "Hooghly", 8: "Howrah",
    9: "Jalpaiguri", 10: "Jhargram", 11: "Kalimpong", 12: "Kolkata",
    13: "Malda", 14: "Murshidabad", 15: "Nadia", 16: "North 24 Parganas",
    17: "Paschim Bardhaman", 18: "Paschim Medinipur", 19: "Purba Bardhaman",
    20: "Purba Medinipur", 21: "Purulia", 22: "South 24 Parganas", 23: "Uttar Dinajpur"
}

# ---------- HELPERS ----------
def safe_float(val):
    try: return float(val)
    except (ValueError, TypeError): return 0.0

def inject_tab_css():
    st.markdown("""
        <style>
        div[data-testid="stTabs"] button[role="tab"] {
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 30px;
            padding: 8px 20px;
            margin-right: 10px;
            font-weight: 600;
            color: #4B5563;
            transition: all 0.25s ease-in-out;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
        div[data-testid="stTabs"] button[role="tab"]:hover {
            background-color: #F3F4F6;
            border-color: #D1D5DB;
            color: #111827;
            transform: translateY(-1px);
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            background-color: #1F77B4 !important;
            color: white !important;
            border-color: #1F77B4 !important;
            box-shadow: 0 4px 10px -2px rgba(31, 119, 180, 0.4) !important;
        }
        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            display: none;
        }
        div[data-testid="stTabs"] [data-baseweb="tab-panel"] {
            padding-top: 25px;
        }
        </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=60)
def fetch_estimate_master():
    supabase = get_supabase()
    return {
        "specs": supabase.table("master_database").select("*").execute().data or [],
        "cons": supabase.table("consumption_matrix").select("*").execute().data or [],
        "lmr": supabase.table("district_lmr_data").select("*").execute().data or [],
        "districts": supabase.table("districts").select("id, district_name").eq("active", True).execute().data or [],
    }

def show():
    require_role('superadmin', 'district')
    user = get_current_user()
    user_role = user.get('role')
    user_district_id = user.get('district_id')

    if user_role == 'district' and not user_district_id:
        st.error("🚨 Your account is missing a District assignment. Please contact Superadmin.")
        st.stop()

    inject_tab_css()
    
    supabase = get_supabase()
    master = fetch_estimate_master()
    df_specs = pd.DataFrame(master["specs"])
    df_cons = pd.DataFrame(master["cons"])
    df_lmr = pd.DataFrame(master["lmr"])
    df_districts = pd.DataFrame(master["districts"])

    tab1, tab2, tab3 = st.tabs(["📋 Master Specifications", "📊 Consumption Matrix", "💰 LMR Rate Management"])

    # ======================== TAB 1: SPECS ========================
    with tab1:
        st.subheader("Master Specifications")
        if not df_specs.empty:
            edited_df = st.data_editor(
                df_specs[['id', 'spec_code', 'description', 'final_unit', 'base_qty']].copy(),
                disabled=["id"],
                column_config={
                    "spec_code": "Spec Code",
                    "description": "Description",
                    "final_unit": "Unit",
                    "base_qty": st.column_config.NumberColumn("Base Quantity", min_value=0.0, format="%.2f")
                },
                hide_index=True,
                use_container_width=True,
                key="specs_editor"
            )
            if st.button("💾 Save Specification Changes", key="save_specs"):
                with st.spinner("Updating..."):
                    for i, row in edited_df.iterrows():
                        if not row.equals(df_specs.iloc[i]):
                            supabase.table("master_database").update({
                                "spec_code": row['spec_code'],
                                "description": row['description'],
                                "final_unit": row['final_unit'],
                                "base_qty": row['base_qty']
                            }).eq("id", row['id']).execute()
                st.success("Saved.")
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("No specifications found.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Add New Specification"):
                st.session_state['show_add_spec'] = True
        with col2:
            if st.button("📤 Bulk Upload Specifications"):
                st.session_state['show_bulk_spec'] = True

        if st.session_state.get('show_add_spec'):
            with st.expander("✏️ Add New Specification", expanded=True):
                with st.form("add_spec_form"):
                    c1, c2 = st.columns(2)
                    new_code = c1.text_input("Spec Code *")
                    new_desc = c2.text_input("Description *")
                    c3, c4 = st.columns(2)
                    new_unit = c3.text_input("Final Unit *")
                    new_qty = c4.number_input("Base Quantity", min_value=0.0, step=0.01, value=0.0)
                    if st.form_submit_button("Add"):
                        if not new_code or not new_desc or not new_unit:
                            st.error("Please fill in required fields.")
                        else:
                            try:
                                supabase.table("master_database").insert({
                                    "spec_code": new_code, "description": new_desc,
                                    "final_unit": new_unit, "base_qty": new_qty
                                }).execute()
                                st.success("Added.")
                                st.session_state['show_add_spec'] = False
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e: st.error(f"Error: {e}")

        if st.session_state.get('show_bulk_spec'):
            with st.expander("📤 Bulk Upload Specifications", expanded=True):
                # --- NEW: Step 1: Download Template ---
                st.markdown("### Step 1: Download Template")
                st.caption("Format: `spec_code`, `description`, `final_unit`, `base_qty`")
                spec_template_cols = ['spec_code', 'description', 'final_unit', 'base_qty']
                spec_template_df = pd.DataFrame(columns=spec_template_cols)
                spec_buf = io.StringIO()
                spec_template_df.to_csv(spec_buf, index=False)
                st.download_button(
                    "📥 Download Specifications Template CSV",
                    data=spec_buf.getvalue(),
                    file_name="master_specifications_template.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                st.markdown("---")
                # --- Step 2: Upload & Process ---
                st.markdown("### Step 2: Upload Filled Template")
                uploaded = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx", "xls"], key="bulk_spec")
                if uploaded:
                    try:
                        df_up = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
                        required = ['spec_code', 'description', 'final_unit', 'base_qty']
                        if all(col in df_up.columns for col in required):
                            st.dataframe(df_up[required], use_container_width=True)
                            if st.button("✅ Insert All", key="exec_bulk_spec"):
                                existing = supabase.table("master_database").select("spec_code").execute().data or []
                                existing_codes = [r['spec_code'] for r in existing]
                                new_recs = [r for r in df_up[required].to_dict('records') if r['spec_code'] not in existing_codes]
                                if new_recs:
                                    supabase.table("master_database").insert(new_recs).execute()
                                    st.success(f"Inserted {len(new_recs)} records.")
                                    st.cache_data.clear()
                                    st.rerun()
                                else: st.warning("All records already exist.")
                        else: st.error(f"Missing columns: {', '.join(required)}")
                    except Exception as e: st.error(f"Error: {e}")

    # ======================== TAB 2: CONSUMPTION MATRIX ========================
    with tab2:
        st.subheader("Consumption Matrix")
        spec_code_list = df_specs['spec_code'].tolist() if not df_specs.empty else []
        
        if not df_cons.empty:
            edited_cons = st.data_editor(
                df_cons[['id', 'spec_code', 'lmr_code', 'consumed_qty']].copy(),
                disabled=["id"],
                column_config={
                    "spec_code": st.column_config.SelectboxColumn("Spec Code", options=spec_code_list if spec_code_list else ["No Specs"]),
                    "lmr_code": "LMR Code",
                    "consumed_qty": st.column_config.NumberColumn("Consumed Qty", min_value=0.0, format="%.4f")
                },
                hide_index=True,
                use_container_width=True,
                key="cons_editor"
            )
            if st.button("💾 Save Consumption Changes", key="save_cons"):
                with st.spinner("Updating..."):
                    for i, row in edited_cons.iterrows():
                        if not row.equals(df_cons.iloc[i]):
                            supabase.table("consumption_matrix").update({
                                "spec_code": row['spec_code'],
                                "lmr_code": row['lmr_code'],
                                "consumed_qty": row['consumed_qty']
                            }).eq("id", row['id']).execute()
                st.success("Saved.")
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("No consumption entries found.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Add Consumption Entry"):
                st.session_state['show_add_cons'] = True
        with col2:
            if st.button("📤 Bulk Upload Consumption"):
                st.session_state['show_bulk_cons'] = True

        if st.session_state.get('show_add_cons'):
            with st.expander("✏️ Add Consumption Entry", expanded=True):
                with st.form("add_cons_form"):
                    if spec_code_list:
                        new_spec_code = st.selectbox("Spec Code *", options=spec_code_list)
                    else:
                        st.warning("No specifications available.")
                        new_spec_code = ""
                    new_lmr_code = st.text_input("LMR Code *")
                    new_qty = st.number_input("Consumed Quantity", min_value=0.0, step=0.1, value=0.0)
                    if st.form_submit_button("Add"):
                        if not new_spec_code or not new_lmr_code:
                            st.error("Fill in required fields.")
                        else:
                            try:
                                supabase.table("consumption_matrix").insert({
                                    "spec_code": new_spec_code, "lmr_code": new_lmr_code, "consumed_qty": new_qty
                                }).execute()
                                st.success("Added.")
                                st.session_state['show_add_cons'] = False
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e: st.error(f"Error: {e}")

        if st.session_state.get('show_bulk_cons'):
            with st.expander("📤 Bulk Upload Consumption", expanded=True):
                # --- NEW: Step 1: Download Template ---
                st.markdown("### Step 1: Download Template")
                st.caption("Format: `spec_code`, `lmr_code`, `consumed_qty`")
                cons_template_cols = ['spec_code', 'lmr_code', 'consumed_qty']
                cons_template_df = pd.DataFrame(columns=cons_template_cols)
                cons_buf = io.StringIO()
                cons_template_df.to_csv(cons_buf, index=False)
                st.download_button(
                    "📥 Download Consumption Template CSV",
                    data=cons_buf.getvalue(),
                    file_name="consumption_matrix_template.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                st.markdown("---")
                # --- Step 2: Upload & Process ---
                st.markdown("### Step 2: Upload Filled Template")
                uploaded = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx", "xls"], key="bulk_cons")
                if uploaded:
                    try:
                        df_up = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
                        required = ['spec_code', 'lmr_code', 'consumed_qty']
                        if all(col in df_up.columns for col in required):
                            st.dataframe(df_up[required], use_container_width=True)
                            if st.button("✅ Insert All", key="exec_bulk_cons"):
                                valid_specs = set(spec_code_list)
                                records = df_up[required].to_dict('records')
                                valid_recs = [r for r in records if r['spec_code'] in valid_specs]
                                if len(records) != len(valid_recs):
                                    st.warning(f"Skipped {len(records)-len(valid_recs)} records with invalid spec_codes.")
                                if valid_recs:
                                    supabase.table("consumption_matrix").insert(valid_recs).execute()
                                    st.success(f"Inserted {len(valid_recs)} entries.")
                                    st.cache_data.clear()
                                    st.rerun()
                                else: st.warning("No valid records to insert.")
                        else: st.error(f"Missing columns: {', '.join(required)}")
                    except Exception as e: st.error(f"Error: {e}")

    # ======================== TAB 3: LMR RATE MANAGEMENT ========================
    with tab3:
        st.subheader("LMR Rate Management")
        
        if not df_lmr.empty:
            df_lmr_view = df_lmr.merge(df_districts, left_on="district_id", right_on="id", how="left")
            df_lmr_view.rename(columns={"district_name": "District"}, inplace=True)

            if user_role == 'superadmin':
                all_d = ["All Districts"] + sorted(df_districts['district_name'].tolist())
                sel_dist = st.selectbox("Filter by District", options=all_d, key="lmr_filter")
                if sel_dist != "All Districts" and sel_dist:
                    filt_id = df_districts[df_districts['district_name'] == sel_dist]['id'].iloc[0]
                    df_lmr_view = df_lmr_view[df_lmr_view['district_id'] == filt_id]
            else:
                user_district_name = df_districts[df_districts['id'] == user_district_id]['district_name'].iloc[0] if not df_districts.empty else "Unknown"
                st.info(f"🔒 You are locked to editing LMR rates for: **{user_district_name}**")
                df_lmr_view = df_lmr_view[df_lmr_view['district_id'] == user_district_id]

            edited_lmr = st.data_editor(
                df_lmr_view[['id', 'District', 'lmr_code', 'description', 'rate', 'unit']].copy(),
                disabled=["id"],
                column_config={
                    "lmr_code": "LMR Code",
                    "description": "Description",
                    "rate": st.column_config.NumberColumn("Rate (₹)", min_value=0.0, format="%.2f"),
                    "unit": "Unit"
                },
                hide_index=True,
                use_container_width=True,
                key="lmr_editor"
            )
            if st.button("💾 Save LMR Changes", key="save_lmr"):
                with st.spinner("Updating..."):
                    for i, row in edited_lmr.iterrows():
                        if not row.equals(df_lmr_view.iloc[i]):
                            supabase.table("district_lmr_data").update({
                                "lmr_code": row['lmr_code'],
                                "description": row['description'],
                                "rate": row['rate'],
                                "unit": row['unit']
                            }).eq("id", row['id']).execute()
                st.success("Saved.")
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("No LMR rates found.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Add New LMR Rate"):
                st.session_state['show_add_lmr'] = True
        with col2:
            if st.button("📤 Bulk Upload LMR (Pivot)"):
                st.session_state['show_bulk_lmr'] = True
                st.rerun()

        if st.session_state.get('show_add_lmr'):
            with st.expander("✏️ Add New LMR Rate", expanded=True):
                with st.form("add_lmr_form"):
                    if user_role == 'superadmin':
                        dist_opts = {d['id']: d['district_name'] for d in master["districts"]}
                        sel_dist_id = st.selectbox("District *", options=list(dist_opts.keys()), format_func=lambda x: dist_opts[x])
                    else:
                        user_district_name = df_districts[df_districts['id'] == user_district_id]['district_name'].iloc[0] if not df_districts.empty else "Unknown"
                        st.markdown(f"**District:** {user_district_name}")
                        sel_dist_id = user_district_id
                    
                    c1, c2 = st.columns(2)
                    lmr_code = c1.text_input("LMR Code *")
                    desc = c2.text_input("Description *")
                    c3, c4 = st.columns(2)
                    rate = c3.number_input("Rate (₹) *", min_value=0.0, step=0.01)
                    unit = c4.text_input("Unit", value="Cum")
                    if st.form_submit_button("Add"):
                        if not lmr_code or not desc:
                            st.error("LMR Code and Description required.")
                        else:
                            try:
                                supabase.table("district_lmr_data").insert({
                                    "district_id": sel_dist_id,
                                    "lmr_code": lmr_code.strip(),
                                    "description": desc.strip(),
                                    "rate": rate,
                                    "unit": unit.strip()
                                }).execute()
                                st.success("Added.")
                                st.session_state['show_add_lmr'] = False
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e: st.error(f"Error: {e}")

        if st.session_state.get('show_bulk_lmr'):
            with st.expander("📤 Bulk Upload LMR (Pivot format)", expanded=True):
                
                # --- Step 1: Download Template ---
                st.markdown("### Step 1: Download Template")
                st.info("Download the CSV template below. Fill it out with your district LMR rates, then proceed to Step 2.")
                
                template_cols = ['lmr_code', 'description', 'unit'] + [f'dist_{i}_rate' for i in range(1, 24)]
                template_df = pd.DataFrame(columns=template_cols)
                lmr_buf = io.StringIO()
                template_df.to_csv(lmr_buf, index=False)
                st.download_button(
                    "📥 Download LMR Pivot Template CSV",
                    data=lmr_buf.getvalue(),
                    file_name="lmr_pivot_template.csv",
                    mime="text/csv",
                    use_container_width=True
                )

                st.markdown("---")

                # --- Step 2: Upload & Process ---
                st.markdown("### Step 2: Upload Filled Template")
                uploaded = st.file_uploader("Upload the filled template", type=["csv", "xlsx", "xls"], key="bulk_lmr")
                
                if uploaded:
                    try:
                        df_up = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
                        df_up.columns = [c.strip().lower() for c in df_up.columns]
                        if all(c in df_up.columns for c in ['lmr_code', 'description']):
                            st.dataframe(df_up, use_container_width=True)
                            if st.button("✅ Process Upload", key="exec_bulk_lmr"):
                                dist_cols = {}
                                for col in df_up.columns:
                                    m = re.match(r'dist_(\d+)_rate', col)
                                    if m and 1 <= int(m.group(1)) <= 23:
                                        dist_cols[int(m.group(1))] = col
                                inserted, errs = 0, []
                                for _, row in df_up.iterrows():
                                    lmr = str(row.get('lmr_code', '')).strip()
                                    desc = str(row.get('description', '')).strip()
                                    unit = str(row.get('unit', 'Cum')).strip()
                                    if not lmr or not desc: continue
                                    for d_id, col_name in dist_cols.items():
                                        rate_val = row.get(col_name)
                                        if pd.isna(rate_val) or rate_val == '': continue
                                        try:
                                            rate = float(rate_val)
                                            existing = supabase.table("district_lmr_data").select("id").eq("lmr_code", lmr).eq("district_id", d_id).execute()
                                            rec = {"district_id": d_id, "lmr_code": lmr, "description": desc, "rate": rate, "unit": unit}
                                            if existing.data:
                                                supabase.table("district_lmr_data").update(rec).eq("id", existing.data[0]['id']).execute()
                                            else:
                                                supabase.table("district_lmr_data").insert(rec).execute()
                                            inserted += 1
                                        except: errs.append(f"Invalid rate for {lmr} in District {d_id}")
                                st.success(f"Processed {inserted} entries.")
                                if errs: st.warning("Partial errors encountered.")
                                st.cache_data.clear()
                                st.rerun()
                        else: st.error("File must contain 'lmr_code' and 'description'")
                    except Exception as e: st.error(f"Error: {e}")
