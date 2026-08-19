import streamlit as st
import pandas as pd
import uuid
import streamlit.components.v1 as components
from utils.db import get_supabase
from auth.auth import get_current_user

# ============================================================
# HELPER FUNCTIONS (self-contained, with safe checks)
# ============================================================

@st.cache_data(ttl=600)
def fetch_master_lookups():
    """Fetch active master data for themes, activities, departments, etc."""
    supabase = get_supabase()
    try:
        return {
            "fys": supabase.table("financial_years").select("*").eq("active", True).execute().data or [],
            "districts": supabase.table("districts").select("*").eq("active", True).execute().data or [],
            "blocks": supabase.table("blocks").select("*").eq("active", True).execute().data or [],
            "depts": supabase.table("departments").select("*").eq("active", True).execute().data or [],
            "wings": supabase.table("department_wings").select("*").execute().data or [],
            "themes": supabase.table("themes").select("*").eq("active", True).execute().data or [],
            "activities": supabase.table("activities").select("*").eq("active", True).execute().data or [],
            "act_dept_mapping": supabase.table("activity_departments").select("*").execute().data or [],
        }
    except Exception:
        return {}

def build_maps(data):
    """Build lookup dictionaries for ids ↔ names."""
    if not data:
        return {}
    return {
        "fy_name_to_id": {str(f["year_name"]).strip(): f["id"] for f in data.get("fys", [])},
        "dist_map": {str(d["district_name"]).strip(): d["id"] for d in data.get("districts", [])},
        "block_map": {str(b["block_name"]).strip(): b["id"] for b in data.get("blocks", [])},
        "dept_map": {str(d["department_name"]).strip(): d["id"] for d in data.get("depts", [])},
        "wing_map": {w["id"]: w for w in data.get("wings", [])},
        "fy_reverse": {f["id"]: f["year_name"] for f in data.get("fys", [])},
        "dist_reverse": {d["id"]: d["district_name"] for d in data.get("districts", [])},
        "block_reverse": {b["id"]: b["block_name"] for b in data.get("blocks", [])},
        "dept_reverse": {d["id"]: d["department_name"] for d in data.get("depts", [])},
    }

def get_filtered_records(supabase, role, user):
    """Fetch convergence records filtered by user's role (district/block/department)."""
    if not isinstance(user, dict):
        return []

    query = supabase.table("convergence_register").select("*")
    if role == "district":
        if not user.get("district_id"):
            return []
        query = query.eq("district_id", user["district_id"])
    elif role == "block":
        if not user.get("block_id"):
            return []
        query = query.eq("block_id", user["block_id"])
    elif role == "department":
        if not user.get("department_id") or not user.get("district_id"):
            return []
        query = query.eq("department_id", user["department_id"]).eq("district_id", user["district_id"])
    # For superadmin, no filter
    try:
        return query.execute().data or []
    except Exception:
        return []

# ============================================================
# MAIN APP
# ============================================================

def show():
    # -------------------- SECURITY --------------------
    if not st.session_state.get('authenticated', False) and not st.session_state.get('is_guest', False):
        st.switch_page("app.py")

    st.set_page_config(
        page_title="SECUReX | Estimate Builder",
        layout="wide",
        initial_sidebar_state="collapsed"   # hide sidebar completely
    )

    # -------------------- CONSTANTS --------------------
    DISTRICT_NAMES = {
        1: "Alipurduar", 2: "Bankura", 3: "Birbhum", 4: "Cooch Behar",
        5: "Dakshin Dinajpur", 6: "Darjeeling", 7: "Hooghly", 8: "Howrah",
        9: "Jalpaiguri", 10: "Jhargram", 11: "Kalimpong", 12: "Kolkata",
        13: "Malda", 14: "Murshidabad", 15: "Nadia", 16: "North 24 Parganas",
        17: "Paschim Bardhaman", 18: "Paschim Medinipur", 19: "Purba Bardhaman",
        20: "Purba Medinipur", 21: "Purulia", 22: "South 24 Parganas", 23: "Uttar Dinajpur"
    }

    UNSKILLED_CODES = ['0115']
    SKILLED_SEMI_CODES = ['0116', '0160', '0161']

    # -------------------- SESSION STATE INIT --------------------
    for key, default in [
        ('work_name', ""),
        ('work_type', ""),
        ('estimate_data', []),
        ('show_dpr', False),
        ('selected_work_id', None),
        ('manual_entry', False),
        ('selected_theme', None),
        ('print_trigger', False)
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # -------------------- SUPABASE CLIENT --------------------
    supabase = get_supabase()

    # -------------------- DATA LOADERS --------------------
    @st.cache_data(ttl=600)
    def load_master_data(district_id, role, department_id):
        try:
            def fetch_all(table, cols="*", filter_col=None, filter_val=None):
                data = []
                start = 0
                limit = 1000
                while True:
                    query = supabase.table(table).select(cols).range(start, start + limit - 1)
                    if filter_col and filter_val is not None:
                        query = query.eq(filter_col, filter_val)
                    res = query.execute()
                    if not res.data:
                        break
                    data.extend(res.data)
                    if len(res.data) < limit:
                        break
                    start += limit
                return data

            specs_data = fetch_all("master_database", "spec_code, description, final_unit, base_qty")
            matrix_data = fetch_all("consumption_matrix", "spec_code, lmr_code, consumed_qty")
            lmr_data = fetch_all("district_lmr_data", "lmr_code, description, rate", "district_id", district_id)

            themes_data = fetch_all("themes", "id, theme_name", "active", True)
            activities_data = fetch_all("activities", "id, theme_id, activity_name", "active", True)
            act_dept_mapping = fetch_all("activity_departments")

            return (
                pd.DataFrame(specs_data),
                pd.DataFrame(matrix_data),
                pd.DataFrame(lmr_data),
                pd.DataFrame(themes_data),
                pd.DataFrame(activities_data),
                pd.DataFrame(act_dept_mapping)
            )
        except Exception:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    user_role = st.session_state.get('role')
    user_dept_id = st.session_state.get('department_id')
    user_district = st.session_state.get('district_id', 1)
    active_district_name = DISTRICT_NAMES.get(user_district, f"District {user_district}")

    df_specs, df_matrix, df_lmr, df_themes, df_activities, df_act_dept = load_master_data(
        user_district, user_role, user_dept_id
    )

    if not df_lmr.empty:
        df_lmr['rate'] = pd.to_numeric(df_lmr['rate'], errors='coerce').fillna(0)

    # -------------------- CONVERGENCE REGISTER INTEGRATION --------------------
    # Get user dict safely
    user = get_current_user() if st.session_state.get('authenticated') else {}
    if not isinstance(user, dict):
        user = {}
    role = user.get('role', 'guest')

    master_lookups = fetch_master_lookups()
    maps = build_maps(master_lookups)

    conv_records = get_filtered_records(supabase, role, user) if role in ['superadmin', 'district', 'block', 'department'] else []
    df_conv = pd.DataFrame(conv_records) if conv_records else pd.DataFrame()

    # Build work options (BUG FIX APPLIED HERE)
    work_options = []
    if not df_conv.empty:
        for _, row in df_conv.iterrows():
            work_options.append({
                'id': row['id'],
                'label': f"{row['activity_description']} (ID: {str(row['id'])[:8]})",
                'work_name': row['activity_description'],
                'theme_id': row.get('thematic_category_id'),
                'row': row
            })

    manual_option = {
        'id': 'manual',
        'label': '✏️ Manual Entry (no register link)',
        'work_name': '',
        'theme_id': None,
        'row': None
    }
    work_options.insert(0, manual_option)

    # -------------------- WATERMARK (for print) --------------------
    try:
        settings_res = supabase.table("system_settings").select("watermark_text").eq("id", 1).execute()
        active_watermark = settings_res.data[0]['watermark_text'] if settings_res.data else 'SECUReX DRAFT'
    except:
        active_watermark = 'SECUReX DRAFT'

    # ============================================================
    # MAIN PAGE LAYOUT (no sidebar)
    # ============================================================

    # ---------- TOP BAR ----------
    top_col1, top_col2, top_col3 = st.columns([2, 3, 1])
    with top_col1:
        st.info(f"📍 **Active District:** {active_district_name}")
    with top_col2:
        view_mode = st.radio(
            "Display Mode",
            ["Edit Workspace", "View Appendix-I Report"],
            horizontal=True,
            label_visibility="collapsed"
        )
    with top_col3:
        if st.button("🔄 Refresh Master Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    # ---------- WORK BASIC DETAILS ----------
    st.markdown("### 📋 Work Basic Details")
    col_sel1, _ = st.columns([3, 1])
    with col_sel1:
        selected_label = st.selectbox(
            "Select Work from Convergence Register",
            options=[opt['label'] for opt in work_options],
            index=0,
            key="work_selector"
        )
    selected_opt = next((opt for opt in work_options if opt['label'] == selected_label), None)

    if selected_opt:
        if selected_opt['id'] == 'manual':
            st.session_state['manual_entry'] = True
            st.session_state['selected_work_id'] = None
        else:
            st.session_state['manual_entry'] = False
            st.session_state['selected_work_id'] = selected_opt['id']
            st.session_state['work_name'] = selected_opt['work_name']

            theme_id = selected_opt['theme_id']
            if theme_id:
                theme_row = df_themes[df_themes['id'] == theme_id]
                st.session_state['selected_theme'] = theme_row.iloc[0]['theme_name'] if not theme_row.empty else "Unknown Theme"
                act_rows = df_activities[df_activities['theme_id'] == theme_id]
                # try to match activity from work name prefix
                work_name = selected_opt['work_name']
                matched = None
                for _, act_row in act_rows.iterrows():
                    if work_name.startswith(act_row['activity_name']):
                        matched = act_row['activity_name']
                        break
                st.session_state['work_type'] = matched if matched else (act_rows.iloc[0]['activity_name'] if not act_rows.empty else "")
            else:
                st.session_state['selected_theme'] = "No Theme"
                st.session_state['work_type'] = ""

    # Display work details
    if st.session_state.get('manual_entry', False):
        with st.container(border=True):
            st.markdown("#### ✏️ Manual Entry")
            st.session_state['work_name'] = st.text_input(
                "Name of Work",
                value=st.session_state['work_name'],
                placeholder="Enter the official project title..."
            )

            if df_activities.empty:
                st.warning("No active activities found.")
                st.session_state['work_type'] = ""
            else:
                df_activities_filtered = df_activities.copy()
                if user_role == 'department' and user_dept_id:
                    df_act_dept['activity_id'] = df_act_dept['activity_id'].astype(str)
                    df_activities_filtered['id'] = df_activities_filtered['id'].astype(str)
                    mapped_ids = df_act_dept[df_act_dept['department_id'] == user_dept_id]['activity_id'].tolist()
                    df_activities_filtered = df_activities_filtered[df_activities_filtered['id'].isin(mapped_ids)]

                if df_activities_filtered.empty:
                    st.warning("No approved activities for your department/jurisdiction.")
                    st.session_state['work_type'] = ""
                else:
                    valid_theme_ids = df_activities_filtered['theme_id'].unique()
                    df_themes_filtered = df_themes[df_themes['id'].isin(valid_theme_ids)]
                    theme_names = ["Select Theme"] + df_themes_filtered['theme_name'].tolist()

                    col_theme, col_act = st.columns(2)
                    with col_theme:
                        sel_theme = st.selectbox("Thematic Work Category", options=theme_names)
                    with col_act:
                        if sel_theme != "Select Theme":
                            selected_theme_id = df_themes_filtered[df_themes_filtered['theme_name'] == sel_theme]['id'].iloc[0]
                            final_activities = df_activities_filtered[df_activities_filtered['theme_id'] == selected_theme_id]
                            final_act_names = final_activities['activity_name'].tolist()
                        else:
                            final_act_names = df_activities_filtered['activity_name'].tolist()

                        if not final_act_names:
                            st.warning("No activities for selected theme.")
                            st.session_state['work_type'] = ""
                        else:
                            current_selection = st.session_state.get('work_type')
                            default_index = 0
                            if current_selection in final_act_names:
                                default_index = final_act_names.index(current_selection)
                            st.session_state['work_type'] = st.selectbox(
                                "Base Activity*",
                                options=final_act_names,
                                index=default_index
                            )
    else:
        if selected_opt and selected_opt['id'] != 'manual':
            st.success(f"**Work Name:** {selected_opt['work_name']}")
            st.info(f"**Theme:** {st.session_state.get('selected_theme', 'Not specified')}")
            st.info(f"**Base Activity:** {st.session_state.get('work_type', 'Not specified')}")
            conv_row = selected_opt.get('row')
            if conv_row is not None:
                dist_name = maps.get('dist_reverse', {}).get(conv_row.get('district_id'), 'N/A')
                block_name = maps.get('block_reverse', {}).get(conv_row.get('block_id'), 'N/A')
                st.caption(f"📍 **District:** {dist_name} | **Block:** {block_name}")
            st.caption("📌 These details are from the Convergence Register. Switch to 'Manual Entry' to edit.")
        else:
            st.warning("Please select a work from the dropdown.")

    # ---------- TOTALS & ACTIONS ----------
    totals = calculate_totals(st.session_state['estimate_data'])
    total_a = totals['unskilled']
    total_b = totals['skilled'] + totals['material'] + totals['gst']
    grand_total = totals['grand_total']

    unskilled_rate = df_lmr[df_lmr['lmr_code'] == '0115']['rate'].iloc[0] if not df_lmr.empty and '0115' in df_lmr['lmr_code'].values else 1
    person_days = (total_a / unskilled_rate) if unskilled_rate > 0 else 0

    col_t1, col_t2, col_t3, col_t4 = st.columns([2, 2, 2, 1])
    col_t1.metric("Component A (Unskilled Labour)", f"₹ {total_a:,.2f}", f"👷 {person_days:,.2f} Person Days", delta_color="off")
    col_t2.metric("Component B (Skilled + Material + GST)", f"₹ {total_b:,.2f}")
    col_t3.success(f"### Grand Total: ₹ {grand_total:,.2f}")
    with col_t4:
        if st.button("🖨️ Print Estimate", use_container_width=True):
            st.session_state['print_trigger'] = True
            st.rerun()

    # Print trigger
    if st.session_state.get('print_trigger', False):
        st.session_state['print_trigger'] = False
        html_report = generate_print_html(
            st.session_state['work_name'],
            st.session_state['work_type'],
            active_district_name,
            active_watermark,
            totals
        )
        components.html(html_report, height=600, scrolling=True)
        if st.button("🔄 Re-print / Download PDF"):
            st.components.v1.html(html_report, height=600, scrolling=True)

    st.markdown("---")

    # ---------- DPR TOGGLE & HEADING BUTTONS ----------
    dpr_toggle = st.checkbox(
        "📄 Show DPR Preview (Optional)",
        value=st.session_state.get('show_dpr', False)
    )
    if dpr_toggle != st.session_state.get('show_dpr', False):
        st.session_state['show_dpr'] = dpr_toggle

    btn_col1, btn_col2, _ = st.columns([2, 2, 6])
    btn_col1.button("➕ Add New Heading", on_click=add_heading, type="primary", use_container_width=True)
    btn_col2.button("📦 Add Lumpsum Heading", on_click=add_lumpsum_heading, use_container_width=True)
    st.markdown("---")

    # ---------- ESTIMATE EDITOR ----------
    if view_mode == "Edit Workspace":
        if df_specs.empty:
            st.warning("Master Data is missing. Please check Supabase setup.")
        else:
            spec_options = [""] + df_specs['spec_code'].tolist()

            for h_idx, heading in enumerate(st.session_state['estimate_data']):
                with st.expander(f"📁 {heading['title']}", expanded=True):
                    col_t, col_del = st.columns([10, 1])
                    heading['title'] = col_t.text_input(
                        "Heading Title",
                        value=heading['title'],
                        key=f"title_{heading['id']}",
                        label_visibility="collapsed"
                    )
                    if col_del.button("🗑️", key=f"del_h_{heading['id']}"):
                        remove_element(st.session_state['estimate_data'], heading['id'])
                        st.rerun()

                    for i_idx, item in enumerate(heading['items']):
                        st.markdown(f"**Item {i_idx + 1}**")
                        if 'material_gsts' not in item:
                            item['material_gsts'] = {}
                        if 'last_spec' not in item:
                            item['last_spec'] = None

                        c1, c2, c3, c4, c5 = st.columns([3, 2, 3, 2, 1])
                        item['input_type'] = c2.radio(
                            "Input Type",
                            ["Direct Quantity", "L × B × D", "Lump Sum (LS)"],
                            key=f"type_{item['id']}",
                            horizontal=True,
                            label_visibility="collapsed"
                        )

                        if item['input_type'] != "Lump Sum (LS)":
                            item['spec_code'] = c1.selectbox(
                                "Specification",
                                spec_options,
                                index=spec_options.index(item['spec_code']) if item['spec_code'] in spec_options else 0,
                                key=f"spec_{item['id']}",
                                format_func=format_spec_dropdown
                            )
                            active_unit = get_spec_unit(item['spec_code'])
                            unit_label = f" ({active_unit})" if active_unit else ""

                            spec_norm = item['spec_code'].strip().upper() if isinstance(item['spec_code'], str) else ""
                            if 'spec_norm' not in df_matrix.columns:
                                df_matrix['spec_norm'] = df_matrix['spec_code'].str.strip().str.upper()
                            recipe = df_matrix[df_matrix['spec_norm'] == spec_norm].copy()

                            if recipe.empty:
                                c4.markdown(f"""
                                <div style='font-size:12px; padding:5px; background-color:#fff3cd; border-radius:5px; border:1px solid #ffeeba;'>
                                    <b style='color:#856404;'>⚠️ No consumption data for this spec</b><br>
                                    Please add entries in the <i>Consumption Matrix</i> (Super Admin).
                                </div>
                                """, unsafe_allow_html=True)
                                unskilled_amt = skilled_amt = mat_amt = item_gst = 0.0
                                item['qty'] = 1.0
                                if item['input_type'] == "L × B × D":
                                    l_col, b_col, d_col = c3.columns(3)
                                    item['L'] = l_col.number_input("L", value=item['L'], key=f"l_{item['id']}")
                                    item['B'] = b_col.number_input("B", value=item['B'], key=f"b_{item['id']}")
                                    item['D'] = d_col.number_input("D", value=item['D'], key=f"d_{item['id']}")
                                    item['qty'] = item['L'] * item['B'] * item['D']
                                else:
                                    item['qty'] = c3.number_input(f"Total Qty{unit_label}", value=item['qty'], key=f"q_{item['id']}")
                            else:
                                if item['input_type'] == "L × B × D":
                                    l_col, b_col, d_col = c3.columns(3)
                                    item['L'] = l_col.number_input("L", value=item['L'], key=f"l_{item['id']}")
                                    item['B'] = b_col.number_input("B", value=item['B'], key=f"b_{item['id']}")
                                    item['D'] = d_col.number_input("D", value=item['D'], key=f"d_{item['id']}")
                                    item['qty'] = item['L'] * item['B'] * item['D']
                                else:
                                    item['qty'] = c3.number_input(f"Total Qty{unit_label}", value=item['qty'], key=f"q_{item['id']}")

                                pure_mats = recipe[~recipe['lmr_code'].isin(UNSKILLED_CODES + SKILLED_SEMI_CODES)]['lmr_code'].tolist()
                                if item['last_spec'] != item['spec_code']:
                                    item['material_gsts'] = {m: 18 for m in pure_mats}
                                    item['last_spec'] = item['spec_code']

                                unskilled_amt, skilled_amt, mat_amt, item_gst, mat_breakdown = calculate_item_cost(
                                    item['spec_code'], item['qty'], item['material_gsts']
                                )

                                c4.markdown(f"""
                                <div style='font-size:12px; line-height:1.2; padding:5px; background-color:#f0f2f6; border-radius:5px;'>
                                    <b style='color:#0056b3;'>Qty: {item['qty']:.2f} {active_unit}</b><br><br>
                                    <b>Unskilled (0115):</b> ₹{unskilled_amt:,.2f}<br>
                                    <b>Skilled/Semi:</b> ₹{skilled_amt:,.2f}<br>
                                    <b>Pure Material:</b> ₹{mat_amt:,.2f}<br>
                                    <b style='color:#d32f2f;'>GST (Aggregated):</b> ₹{item_gst:,.2f}
                                </div>
                                """, unsafe_allow_html=True)

                                if pure_mats:
                                    with st.expander("⚙️ Configure Material GST Slabs", expanded=False):
                                        cols = st.columns(min(len(pure_mats), 3))
                                        for idx, m_code in enumerate(pure_mats):
                                            col_idx = idx % 3
                                            m_desc = df_lmr[df_lmr['lmr_code'] == m_code]['description'].iloc[0] if not df_lmr[df_lmr['lmr_code'] == m_code].empty else "Unknown"
                                            item['material_gsts'][m_code] = cols[col_idx].selectbox(
                                                f"{m_code} - {m_desc[:15]}...",
                                                [0, 5, 12, 18, 28],
                                                index=[0, 5, 12, 18, 28].index(item['material_gsts'].get(m_code, 18)),
                                                key=f"gst_{item['id']}_{m_code}",
                                                format_func=lambda x: f"{x}%"
                                            )
                        else:
                            item['ls_desc'] = c1.text_input("Lump Sum Type", value=item.get('ls_desc', ''), key=f"ls_d_{item['id']}")
                            item['ls_amount'] = c3.number_input("Direct Amount (₹)", value=item.get('ls_amount', 0.0), key=f"ls_m_{item['id']}")
                            c4.markdown(f"""
                            <div style='font-size:12px; padding:5px; background-color:#e8f4f8; border-radius:5px;'>
                                <b style='color:#0056b3;'>Qty: 1 (LS)</b><br><br>
                                <b>Lump Sum Amount:</b> ₹{item['ls_amount']:,.2f}<br>
                                <b style='color:#d32f2f;'>GST Exempt (0%)</b>
                            </div>
                            """, unsafe_allow_html=True)
                            unskilled_amt = 0.0
                            skilled_amt = 0.0
                            mat_amt = item['ls_amount']
                            item_gst = 0.0
                            item['spec_code'] = 'LS'
                            item['qty'] = 1

                        if c5.button("❌", key=f"del_i_{item['id']}"):
                            remove_element(heading['items'], item['id'])
                            st.rerun()
                        st.markdown("<hr style='margin: 0px; padding: 0px; border-top: 1px dashed #ddd;'>", unsafe_allow_html=True)

                    item_add_col1, item_add_col2 = st.columns([3, 7])
                    item_add_col1.button(
                        "↳ Add Standard Item",
                        key=f"add_i_{heading['id']}",
                        on_click=add_item,
                        args=(heading['id'], False)
                    )
                    item_add_col2.button(
                        "↳ Add Lump Sum Item",
                        key=f"add_ls_{heading['id']}",
                        on_click=add_item,
                        args=(heading['id'], True)
                    )

    elif view_mode == "View Appendix-I Report":
        st.info("Report preview uses the identical calculation engine. Make sure to refine values in 'Edit Workspace' mode.")

    # ---------- DPR SUMMARY (if enabled) ----------
    if st.session_state.get('show_dpr', False):
        st.markdown("---")
        st.markdown("**📊 DPR Summary**")
        for detail in totals['item_details']:
            if detail['materials']:
                with st.expander(f"{detail['spec_code']} - {detail['description']}"):
                    df_mat = pd.DataFrame(detail['materials'])
                    st.dataframe(
                        df_mat[['lmr_code', 'description', 'multiplier', 'rate', 'amount', 'gst_rate', 'gst_amount']],
                        hide_index=True,
                        use_container_width=True
                    )
        st.caption("DPR Preview (materials & GST)")

    # ---------- TEMPLATES SECTION ----------
    st.markdown("---")
    with st.expander("💾 Approved Templates", expanded=False):
        try:
            temp_res = supabase.table("saved_templates").select("id, template_name, estimate_data").execute()
            saved_templates = temp_res.data
        except:
            saved_templates = []

        if saved_templates:
            for t in saved_templates:
                col1, col2, col3 = st.columns([6, 1, 1])
                col1.write(f"📄 {t['template_name']}")
                if col2.button("📂 Load", key=f"ld_{t['id']}", use_container_width=True):
                    st.session_state['estimate_data'] = t['estimate_data']
                    st.toast(f"Loaded '{t['template_name']}'.")
                    st.rerun()
                if st.session_state.get('authenticated') and st.session_state.get('role') in ['SuperAdmin', 'StateAdmin', 'DistrictAdmin']:
                    if col3.button("🗑️", key=f"dl_{t['id']}", use_container_width=True):
                        supabase.table("saved_templates").delete().eq("id", t['id']).execute()
                        st.rerun()
        else:
            st.caption("No templates saved yet.")

        if st.session_state.get('authenticated') and st.session_state.get('role') in ['SuperAdmin', 'StateAdmin', 'DistrictAdmin']:
            if st.button("➕ Save Current as New Template", use_container_width=True):
                if not st.session_state['estimate_data']:
                    st.error("Cannot save an empty estimate!")
                else:
                    user_name = st.session_state.get('full_name', 'Engineer')
                    new_t_name = f"Template {len(saved_templates) + 1} ({user_name})"
                    supabase.table("saved_templates").insert({
                        "owner_name": user_name,
                        "template_name": new_t_name,
                        "estimate_data": st.session_state['estimate_data']
                    }).execute()
                    st.toast("Template saved!")
                    st.rerun()

    # ============================================================
    # HELPER FUNCTIONS (defined inside show to capture dataframes)
    # ============================================================
    def format_spec_dropdown(code):
        if not code:
            return "Select Specification..."
        try:
            row = df_specs[df_specs['spec_code'] == code].iloc[0]
            desc = str(row['description'])[:50] + "..." if len(str(row['description'])) > 50 else str(row['description'])
            unit = str(row['final_unit'])
            return f"{code} | {desc} ({unit})"
        except:
            return code

    def get_spec_unit(code):
        if not code or code == 'LS' or df_specs.empty:
            return ""
        try:
            return str(df_specs[df_specs['spec_code'] == code]['final_unit'].iloc[0])
        except:
            return ""

    def add_heading():
        st.session_state['estimate_data'].append({
            'id': str(uuid.uuid4()),
            'type': 'heading',
            'title': f"New Heading {len(st.session_state['estimate_data']) + 1}",
            'items': []
        })

    def add_lumpsum_heading():
        st.session_state['estimate_data'].append({
            'id': str(uuid.uuid4()),
            'type': 'heading',
            'title': f"Lump Sum Section {len(st.session_state['estimate_data']) + 1}",
            'items': [{
                'id': str(uuid.uuid4()),
                'spec_code': 'LS',
                'input_type': 'Lump Sum (LS)',
                'L': 1.0,
                'B': 1.0,
                'D': 1.0,
                'qty': 1.0,
                'ls_desc': 'Contingency / Site Clearance',
                'ls_amount': 0.0,
                'material_gsts': {},
                'last_spec': None
            }]
        })

    def add_item(heading_id, is_ls=False):
        for h in st.session_state['estimate_data']:
            if h['id'] == heading_id:
                h['items'].append({
                    'id': str(uuid.uuid4()),
                    'spec_code': 'LS' if is_ls else None,
                    'input_type': 'Lump Sum (LS)' if is_ls else 'Direct Quantity',
                    'L': 1.0,
                    'B': 1.0,
                    'D': 1.0,
                    'qty': 1.0,
                    'ls_desc': '',
                    'ls_amount': 0.0,
                    'material_gsts': {},
                    'last_spec': None
                })

    def remove_element(element_list, element_id):
        element_list[:] = [e for e in element_list if e.get('id') != element_id]

    def calculate_item_cost(spec_code, final_qty, material_gsts_dict):
        if not spec_code or df_matrix.empty or df_lmr.empty:
            return 0.0, 0.0, 0.0, 0.0, []
        try:
            base_qty = float(df_specs[df_specs['spec_code'] == spec_code]['base_qty'].iloc[0])
        except:
            return 0.0, 0.0, 0.0, 0.0, []

        spec_norm = spec_code.strip().upper()
        df_matrix['spec_norm'] = df_matrix['spec_code'].str.strip().str.upper()
        recipe = df_matrix[df_matrix['spec_norm'] == spec_norm].copy()
        if recipe.empty:
            return 0.0, 0.0, 0.0, 0.0, []

        cost_data = pd.merge(recipe, df_lmr, on='lmr_code', how='left')
        cost_data['multiplier'] = (pd.to_numeric(cost_data['consumed_qty'], errors='coerce') / base_qty) * final_qty
        cost_data['amount'] = cost_data['multiplier'] * cost_data['rate']

        unskilled = cost_data[cost_data['lmr_code'].isin(UNSKILLED_CODES)]['amount'].sum()
        skilled = cost_data[cost_data['lmr_code'].isin(SKILLED_SEMI_CODES)]['amount'].sum()
        pure_materials = cost_data[~cost_data['lmr_code'].isin(UNSKILLED_CODES + SKILLED_SEMI_CODES)]
        pure_material_cost = pure_materials['amount'].sum()

        total_gst = 0.0
        material_breakdown = []
        for _, row in pure_materials.iterrows():
            mat_code = row['lmr_code']
            gst_pct = material_gsts_dict.get(mat_code, 18)
            gst_amt = row['amount'] * (gst_pct / 100.0)
            total_gst += gst_amt
            material_breakdown.append({
                'lmr_code': mat_code,
                'description': row['description'],
                'multiplier': row['multiplier'],
                'rate': row['rate'],
                'amount': row['amount'],
                'gst_rate': gst_pct,
                'gst_amount': gst_amt
            })
        return unskilled, skilled, pure_material_cost, total_gst, material_breakdown

    def calculate_totals(estimate_data):
        total_unskilled = 0.0
        total_skilled = 0.0
        total_material = 0.0
        total_gst = 0.0
        item_details = []

        for heading in estimate_data:
            for item in heading.get('items', []):
                if item['input_type'] == "Lump Sum (LS)":
                    ls_amt = item.get('ls_amount', 0.0)
                    total_material += ls_amt
                    item_details.append({
                        'heading': heading['title'],
                        'spec_code': 'LS',
                        'description': item.get('ls_desc', 'Lump Sum'),
                        'qty': 1,
                        'unit': 'LS',
                        'unskilled': 0.0,
                        'skilled': 0.0,
                        'material': ls_amt,
                        'gst': 0.0,
                        'total': ls_amt,
                        'materials': []
                    })
                else:
                    spec = item.get('spec_code')
                    if not spec:
                        continue
                    qty = item.get('qty', 0.0)
                    gsts = item.get('material_gsts', {})
                    unsk, skilled, mat, gst, mat_break = calculate_item_cost(spec, qty, gsts)
                    total_unskilled += unsk
                    total_skilled += skilled
                    total_material += mat
                    total_gst += gst
                    try:
                        spec_desc = df_specs[df_specs['spec_code'] == spec]['description'].iloc[0]
                    except:
                        spec_desc = spec
                    item_details.append({
                        'heading': heading['title'],
                        'spec_code': spec,
                        'description': spec_desc,
                        'qty': qty,
                        'unit': get_spec_unit(spec),
                        'unskilled': unsk,
                        'skilled': skilled,
                        'material': mat,
                        'gst': gst,
                        'total': unsk + skilled + mat + gst,
                        'materials': mat_break
                    })

        grand_total = total_unskilled + total_skilled + total_material + total_gst
        return {
            'unskilled': total_unskilled,
            'skilled': total_skilled,
            'material': total_material,
            'gst': total_gst,
            'grand_total': grand_total,
            'item_details': item_details
        }

    def generate_print_html(work_name, work_type, district_name, watermark, totals):
        html = f"""
        <html>
        <head><style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .watermark {{ color: #ccc; font-size: 14px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .totals {{ margin-top: 30px; font-weight: bold; }}
            .grand {{ font-size: 18px; color: #d32f2f; }}
        </style></head>
        <body>
        <div class="header">
            <h2>Appendix-I: Estimate of {work_name}</h2>
            <p><strong>Scheme:</strong> {work_type}</p>
            <p><strong>District:</strong> {district_name}</p>
            <p class="watermark">{watermark}</p>
        </div>
        <table>
            <thead><tr><th>Heading</th><th>Item</th><th>Spec Code</th><th>Qty</th><th>Unit</th><th>Unskilled</th><th>Skilled</th><th>Material</th><th>GST</th><th>Total</th></tr></thead>
            <tbody>
        """
        for detail in totals['item_details']:
            html += f"""
            <tr>
                <td>{detail['heading']}</td>
                <td>{detail['description']}</td>
                <td>{detail['spec_code']}</td>
                <td>{detail['qty']:.2f}</td>
                <td>{detail['unit']}</td>
                <td>₹{detail['unskilled']:,.2f}</td>
                <td>₹{detail['skilled']:,.2f}</td>
                <td>₹{detail['material']:,.2f}</td>
                <td>₹{detail['gst']:,.2f}</td>
                <td>₹{detail['total']:,.2f}</td>
            </tr>
            """
        html += f"""
            </tbody>
            <tfoot>
                <tr><th colspan="5">Totals</th>
                    <th>₹{totals['unskilled']:,.2f}</th>
                    <th>₹{totals['skilled']:,.2f}</th>
                    <th>₹{totals['material']:,.2f}</th>
                    <th>₹{totals['gst']:,.2f}</th>
                    <th>₹{totals['grand_total']:,.2f}</th>
                </tr>
            </tfoot>
        </table>
        <div class="totals">
            <p>Component A (Unskilled): ₹{totals['unskilled']:,.2f}</p>
            <p>Component B (Skilled + Material + GST): ₹{totals['skilled']+totals['material']+totals['gst']:,.2f}</p>
            <p class="grand">Grand Total: ₹{totals['grand_total']:,.2f}</p>
        </div>
        <p style="margin-top: 40px; color: #888; font-size: 12px;">Generated by SECUReX on {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
        <script>window.onload = function() {{ window.print(); }}</script>
        </body></html>
        """
        return html
