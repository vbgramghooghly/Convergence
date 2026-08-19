import streamlit as st
import pandas as pd
from datetime import date, datetime
import io
import re
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

CONVERGENCE_TYPES = [
    "Technical Convergence (Zero Fund/NOC)",
    "Financial (as PIA)",
    "Financial (as Non-PIA)",
]
PIA_OPTIONS = ["Select PIA", "GP", "Block", "Department", "Other"]

# ---------- HOOGHLY DISTRICT BLOCK → GP MAPPING ----------
HOOGHLY_GPS = {
    "CHINSURAH MOGRA": ["BANDEL", "CHANDRAHATI-I", "CHANDRAHATI-II", "DEBANANDAPUR", "DIGSUIHOYERA", "KODALIA-I", "KODALIA-II", "MOGRA-I", "MOGRA-II", "SAPTAGRAM"],
    "POLBA DADPUR": ["AKHNA", "AMNAN", "BABNAN", "DADPUR", "GOSWAMIMALIPARA", "HARIT", "MAHANAD", "MAKALPUR", "POLBA", "RAJHAT", "SATITHAN", "SUGANDHA"],
    "DHANIAKHALI": ["BELMURI", "BHANDARHATI-I", "BHANDARHATI-II", "BHASTARA", "DASHGHARA-I", "DASHGHARA-II", "DHANEKHALI-I", "DHANEKHALI-II", "GOPINATHPUR-I", "GOPINATHPUR-II", "GUDUBARI-I", "GUDUBARI-II", "GURAP", "KHAJUDAHAMILKI", "MANDRA", "PERAMBUASAHABAZAR", "SOMASPUR-I", "SOMASPUR-II"],
    "PANDUA": ["BANTIKABAINCHI", "BELOONDHAMASIN", "BERELAKONCHMALI", "HARALDASPUR", "ITACHUNAKHANYAN", "JAMNA", "JAMNAGARMONDALAII", "JAYERDWARBASINI", "KSHIRKUNDI-NAMAJGRAM-NIYASA", "LCHHOBADASPUR", "PANCHAGARA-TOREGRAM", "PANDUA", "RAMESWARPUR-GOPALNAGAR", "SARAI-TINNA", "SHIKHIRACHANPTA", "SIMLAGARHVITASIN"],
    "BALAGARH": ["BAKLIADHOBAPARA", "CHARKRISHNABATI", "DUMURDAHANITYANANDAPUR-I", "DUMURDAHANITYANANDAPUR-II", "EKTARPUR", "GUPTIPARA-I", "GUPTIPARA-II", "JIRAT", "MOHIPALPUR", "SIJAKAMALPUR", "SOMRA-I", "SOMRA-II", "SRIPUR-BALAGARH"],
    "SINGUR": ["ANANDANAGAR", "BAGDANGACHINAMORE", "BAINCHIPOTA", "BALARAMBATI", "BARUIPARAPALTAGARH", "BASUBATI", "BERABERI", "BIGHATI", "BORA", "BORAIPAHALAMPUR", "GOPALNAGAR", "KAMARKUNDUGOPALNAGARDALUIGACHHA", "MIRZAPURBANKIPUR", "NASIBPUR", "SINGUR-I", "SINGUR-II"],
    "HARIPAL": ["HARIPALASHUTOSH", "ALIPURKASHIPUR", "BANDIPUR", "CHANDANPUR", "DWARHATTA", "HARIPALKINGKARBATI", "HARIPALSAHADEV", "JEJUR", "KAIKALA", "NALIKULPASCHIM", "NALIKULPURBA", "NARAYANPURBAHIRKHANDA", "PASCHIMGOPINATHPUR", "PYANTRA", "SRIPATIPURILIPUR"],
    "TARAKESWAR": ["ASHTARADATTAPUR", "BALIGORI-I", "BALIGORI-II", "BHANJIPUR", "CHAMPADANGA", "KESABCHAK", "NAITAMALPAHARPUR", "PURBARAMNAGAR", "SANTOSHPUR", "TALPUR"],
    "SERAMPORE UTTARPARA": ["KANAIPUR", "NABAGRAM", "PAYARAPUR", "RAGHUNATHPUR", "RAJYADHARPUR", "RISHRA"],
    "CHANDITALA I": ["AINYA", "BHAGABATIPUR", "GANGADHARPUR", "HARIPUR", "KRISHNARAMPUR", "KUMIRMORE", "MASAT", "NABABPUR", "SHIYAKHALA"],
    "CHANDITALA II": ["BAKSA", "BARIJHATI", "BEGUMPUR", "CHANDITALA", "GARALGACHHA", "JANAI", "KAPASARIA", "NAITI", "PANCHGHORA"],
    "JANGIPARA": ["ANTPUR", "DILAKASH", "FURFURA", "JANGIPARA", "KOTALPUR", "MUNDALIKA", "RADHANAGAR", "RAJBALHAT-I", "RAJBALHAT-II", "RASIDPUR"],
    "GOGHAT I": ["BALI", "BHADUR", "GOGHAT", "KUMARSA", "NAKUNDA", "RAGHUBATI", "SAORA"],
    "GOGHAT II": ["BADANGANJ-FALUI-I", "BADANGANJ-FALUI-II", "BENGAI", "HAZIPUR", "KAMARPUKUR", "KUMARGANJ", "MANDARAN", "PASCHIMPARA", "SHYAMBAZAR"],
    "ARAMBAGH": ["ARANDI-I", "ARANDI-II", "BATANAL", "GOURHATI-I", "GOURHATI-II", "HARINKHOLA-I", "HARINKHOLA-II", "MADHABPUR", "MALAYPUR-I", "MALAYPUR-II", "MAYAPUR-I", "MAYAPUR-II", "SALEPUR-I", "SALEPUR-II", "TIROLE"],
    "KHANAKUL I": ["ARUNDA", "BALIPUR", "GHOSHPUR", "KHANAKUL-I", "KHANAKUL-II", "KISHOREPUR-I", "KISHOREPUR-II", "POLE-I", "POLE-II", "RAMMOHAN-I", "RAMMOHAN-II", "TANTISAL", "THAKURANICHAK"],
    "KHANAKUL II": ["CHINGRA", "DHANYAGORI", "JAGATPUR", "MAROKHANA", "NATIBPUR-I", "NATIBPUR-II", "PALASHPAI-I", "PALASHPAI-II", "RAJHATI-I", "RAJHATI-II", "SABALSINGHAPUR"],
    "PURSURAH": ["BHANGAMORA", "CHILADANGI", "DIHIBADPUR", "KELEPARA", "PURSURAH-I", "PURSURAH-II", "SHYAMPUR", "SREERAMPUR"]
}

def safe_int(val):
    if pd.isna(val) or val is None or val == '':
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0

@st.cache_data(ttl=600)
def fetch_master_data():
    supabase = get_supabase()
    try:
        departments = supabase.table("departments").select("id,department_name").execute().data or []
        wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").execute().data or []
        districts = supabase.table("districts").select("id,district_name").execute().data or []
        blocks = supabase.table("blocks").select("id,block_name,district_id").execute().data or []
        activities = supabase.table("activities").select("*").eq("active", True).execute().data or []
        act_dept_mapping = supabase.table("activity_departments").select("*").execute().data or []
        fys = supabase.table("financial_years").select("*").eq("active", True).execute().data or []
        users_data = supabase.table("users").select("id, full_name, role, department_id, wing_id, district_id, block_id").execute().data or []
        themes = supabase.table("themes").select("id,theme_name").eq("active", True).execute().data or []
        return departments, wings, districts, blocks, activities, act_dept_mapping, fys, users_data, themes
    except Exception:
        return [], [], [], [], [], [], [], [], []

def safe_parse_date(date_val):
    if pd.isna(date_val) or not date_val:
        return None
    try:
        if isinstance(date_val, str):
            return pd.to_datetime(date_val).date()
        return date_val
    except Exception:
        return None

def show():
    require_role('superadmin', 'district', 'block', 'department')
    user = get_current_user()
    role = user['role']
    supabase = get_supabase()
    
    departments, wings, districts, blocks, activities, act_dept_mapping, fys, users_data, themes = fetch_master_data()
    
    dept_map = {d['id']: d['department_name'] for d in departments}
    wing_map = {w['id']: w for w in wings}
    dist_map = {d['id']: d['district_name'] for d in districts}
    block_map = {b['id']: b['block_name'] for b in blocks}
    block_name_to_id = {b['block_name']: b['id'] for b in blocks}
    dept_to_wings = {}
    for w in wings:
        dept_to_wings.setdefault(w['department_id'], []).append(w)
    
    t_dists = districts if role in ['superadmin', 'district'] else [d for d in districts if d['id'] == user.get('district_id')]
    t_dist_dict = {d['district_name']: d['id'] for d in t_dists}
    
    fy_id_to_name = {f["id"]: f["year_name"].strip() for f in fys}
    if not fy_id_to_name:
        st.error("⚠️ No active Financial Years found in the database. Please contact your administrator.")
        st.stop()

    active_fy = st.session_state.get("selected_fy", "2026-27")
    active_fy_id = None
    for f in fys:
        if f.get('year_name') == active_fy:
            active_fy_id = f['id']
            break

    # UPDATE: Added tab5 with the new Audit Trail
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎯 Department Targets (Planning)", 
        "🏗️ Implementation Progress (Execution)", 
        "🤝 Meeting Commitments (Sync)",
        "🚨 Target Compliance",
        "📋 Progress Audit Trail & History"
    ])

    # ================= TAB 1: REDESIGNED (Removed optional remarks) =================
    with tab1:
        query_t = supabase.table("department_targets").select("*")
        if role == 'department':
            query_t = query_t.eq("department_id", user.get('department_id')).eq("district_id", user.get('district_id'))
            if user.get('wing_id'):
                query_t = query_t.eq("wing_id", user.get('wing_id'))
            else:
                query_t = query_t.is_("wing_id", "null")
        elif role in ['district', 'block']:
            query_t = query_t.eq("district_id", user.get('district_id'))
        
        data_t = query_t.execute().data
        df_t = pd.DataFrame(data_t) if data_t else pd.DataFrame()

        if not df_t.empty:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total Activities Targeted", len(df_t))
            k2.metric("Total Planned Assets", int(pd.to_numeric(df_t['asset_count'], errors='coerce').sum()))
            k3.metric("Converged Dept Fund (₹L)", f"₹{pd.to_numeric(df_t['department_fund'], errors='coerce').sum():,.2f}")
            k4.metric("Total Persondays Planned", f"{int(pd.to_numeric(df_t['expected_persondays'], errors='coerce').sum()):,}")
            st.markdown("<br>", unsafe_allow_html=True)

        col_t1, col_t2 = st.columns([1.6, 1], gap="large")
        
        with col_t2:
            st.markdown("#### 📝 Add / Update Block‑wise Targets")
            if role == 'block':
                st.info("Target setting is managed at the District/Department level.")
            else:
                with st.container(border=True):
                    active_dept_id, active_wing_id, dist_id = None, None, None
                    
                    # ---- CARD 1: TARGET CONFIGURATION (compact) ----
                    col1, col2, col3 = st.columns(3)
                    
                    selected_fy_target_id = col1.selectbox(
                        "Financial Year*",
                        options=list(fy_id_to_name.keys()),
                        format_func=lambda x: fy_id_to_name[x]
                    )
                    selected_fy_year = fy_id_to_name.get(selected_fy_target_id, '')

                    if role == 'department':
                        active_dept_id = user.get('department_id')
                        active_wing_id = user.get('wing_id')
                        dept_name = dept_map.get(active_dept_id, "Unknown Department")
                        if active_wing_id and active_wing_id in wing_map:
                            display_text = f"{dept_name} ➔ {wing_map[active_wing_id]['wing_name']}"
                        else:
                            display_text = f"{dept_name} (Main Department)"
                        col2.markdown(f"<span style='color:#64748B; font-size:12px;'>DEPARTMENT / WING</span><br>**{display_text}**", unsafe_allow_html=True)
                        dist_sel = list(t_dist_dict.keys())[0] if t_dist_dict else None
                        dist_id = user.get('district_id')
                        col3.markdown(f"<span style='color:#64748B; font-size:12px;'>DISTRICT</span><br>**{dist_sel}**", unsafe_allow_html=True)
                    else:
                        dept_options = [{"label": f"{d['department_name']} (Main Department)", "dept_id": d['id'], "wing_id": None} for d in departments]
                        for w in wings:
                            p_name = dept_map.get(w['department_id'], "Unknown Department")
                            dept_options.append({"label": f"{p_name} ➔ {w['wing_name']} [{w['entity_type']}]", "dept_id": w['department_id'], "wing_id": w['id']})
                        dept_options = sorted(dept_options, key=lambda x: x['label'])
                        dept_labels = [opt['label'] for opt in dept_options]
                        sel_dept_label = col2.selectbox("Department / Wing*", dept_labels)
                        selected_opt = next(opt for opt in dept_options if opt['label'] == sel_dept_label)
                        active_dept_id, active_wing_id = selected_opt['dept_id'], selected_opt['wing_id']
                        dist_sel = col3.selectbox("District*", list(t_dist_dict.keys()) if t_dist_dict else ["None"])
                        dist_id = t_dist_dict.get(dist_sel)

                    # Project Head in its own row
                    PROJECT_HEAD_OPTIONS = [
                        "Canals, Check Dams & Dykes",
                        "Ponds & Water Harvesting",
                        "Wells & Micro-Irrigation",
                        "Waterlogged Land Reclamation",
                        "Afforestation & Plantations",
                        "Rooftop Rainwater Harvesting",
                        "Rural Roads & Culverts",
                        "GP Bhawans & Public Buildings",
                        "School Infrastructure & Playgrounds",
                        "Crematoria & Graveyards",
                        "Solid & Liquid Waste Management",
                        "Solar & Renewable Energy",
                        "Parking, Sheds & Amenities",
                        "Rural Housing (PMAY-G)",
                        "Jal Jeevan Mission Maintenance",
                        "Skill Centres & Work Sheds",
                        "Rural Haats & Markets",
                        "Agri-Storage & Cold Chains",
                        "SHG & Federation Buildings",
                        "Compost Structures",
                        "Livestock Shelters & Dairy",
                        "Fisheries & Aquaculture",
                        "Nurseries & Building Materials",
                        "Circular Economy Processing Units",
                        "Disaster & Cyclone Shelters",
                        "Embankments & Mitigation Works",
                        "Post-Disaster Restoration"
                    ]
                    selected_theme_name = st.selectbox("Convergence Project Head*", PROJECT_HEAD_OPTIONS)

                    # ---- CARD 2: ANNUAL PLAN & CONVERGENCE (compact, remarks removed) ----
                    with st.container(border=True):
                        st.markdown("##### Annual Plan & Convergence")
                        col_scope, col_scheme = st.columns([1, 2])
                        
                        with col_scope:
                            annual_plan_scope = st.text_area("Scope under Annual Plan", height=80)
                        
                        with col_scheme:
                            # Scheme Convergence in a compact grid
                            conv_col1, conv_col2 = st.columns(2)
                            with conv_col1:
                                conv_choice = st.radio(
                                    "Convergence with Own Departmental Scheme / Fund?",
                                    options=["No", "Yes"],
                                    key="conv_choice_target",
                                    index=0
                                )
                                scheme_name = ""
                                if conv_choice == "Yes":
                                    scheme_name = st.text_input(
                                        "Name of Departmental Scheme / Fund *",
                                        key="scheme_name_target"
                                    )
                            with conv_col2:
                                status_options = ["Yes", "No", "Not Confirmed"]
                                annual_plan_status = st.selectbox(
                                    "Included in Department's Own Annual Plan?",
                                    options=status_options,
                                    key="annual_plan_status_target"
                                )
                                # REMOVED: Departmental Scheme / Annual Plan Remarks (Optional)

                    # ---- CARD 3: BLOCK-WISE TARGET ENTRIES (LARGE) ----
                    st.markdown("---")
                    st.markdown("#### 📋 Block‑wise Target Entries")

                    # Get blocks for the district
                    if dist_id:
                        dist_blocks = [b for b in blocks if b['district_id'] == dist_id]
                    else:
                        dist_blocks = blocks
                    block_options = {b['block_name']: b['id'] for b in dist_blocks}
                    block_names = list(block_options.keys())

                    # Get activities for the department
                    valid_activity_ids = [m['activity_id'] for m in act_dept_mapping if m['department_id'] == active_dept_id]
                    valid_activities = [a for a in activities if a['id'] in valid_activity_ids]
                    activity_options = {a['activity_name']: a['id'] for a in valid_activities}
                    activity_names = list(activity_options.keys())

                    # Fetch existing targets
                    existing_targets = []
                    if active_dept_id and dist_id and selected_fy_target_id:
                        q_existing = supabase.table("department_targets").select("*") \
                            .eq("department_id", active_dept_id) \
                            .eq("district_id", dist_id) \
                            .eq("financial_year_id", selected_fy_target_id)
                        if active_wing_id:
                            q_existing = q_existing.eq("wing_id", active_wing_id)
                        else:
                            q_existing = q_existing.is_("wing_id", "null")
                        existing_targets = q_existing.execute().data or []

                    # Build DataFrame
                    if existing_targets:
                        rows = []
                        for t in existing_targets:
                            act_name = t.get('activity', '')
                            block_id = t.get('block_id')
                            block_name = block_map.get(block_id, '')
                            if not block_name:
                                continue
                            rows.append({
                                "Block": block_name,
                                "Approved Activity": act_name,
                                "Desired Target": t.get('desired_target', 0),
                                "Dept Fund (₹ Lakhs)": float(t.get('department_fund', 0.0)),
                                "VB-G Fund (₹ Lakhs)": float(t.get('vbgramg_fund', 0.0)),
                                "Expected Persondays": t.get('expected_persondays', 0)
                            })
                        df_editor = pd.DataFrame(rows)
                    else:
                        df_editor = pd.DataFrame({
                            "Block": [""],
                            "Approved Activity": [""],
                            "Desired Target": [1],
                            "Dept Fund (₹ Lakhs)": [0.0],
                            "VB-G Fund (₹ Lakhs)": [0.0],
                            "Expected Persondays": [0]
                        })

                    # ---- DATA EDITOR (LARGE) ----
                    edited_df = st.data_editor(
                        df_editor,
                        use_container_width=True,
                        num_rows="dynamic",
                        height=450,
                        column_config={
                            "Block": st.column_config.SelectboxColumn(
                                "Block*",
                                options=block_names,
                                required=True
                            ),
                            "Approved Activity": st.column_config.SelectboxColumn(
                                "Approved Activity / Work Category*",
                                options=activity_names,
                                required=True
                            ),
                            "Desired Target": st.column_config.NumberColumn(
                                "Desired Target",
                                min_value=0,
                                step=1,
                                required=True
                            ),
                            "Dept Fund (₹ Lakhs)": st.column_config.NumberColumn(
                                "Dept Fund (₹ Lakhs)",
                                min_value=0.0,
                                step=0.1,
                                format="%.2f"
                            ),
                            "VB-G Fund (₹ Lakhs)": st.column_config.NumberColumn(
                                "VB-G Fund (₹ Lakhs)",
                                min_value=0.0,
                                step=0.1,
                                format="%.2f"
                            ),
                            "Expected Persondays": st.column_config.NumberColumn(
                                "Expected Persondays*",
                                min_value=0,
                                step=1,
                                required=True
                            )
                        },
                        hide_index=True
                    )

                    # ---- SAVE BUTTON ----
                    if st.button("💾 Save All Targets", type="primary", use_container_width=True):
                        # ---- LOGIC COMPLETELY UNCHANGED (except remarks removed) ----
                        errors = []
                        if not active_dept_id or not dist_id:
                            errors.append("Invalid Department or District.")
                        if not selected_theme_name:
                            errors.append("Please select a valid Convergence Project Head.")
                        if edited_df.empty or edited_df.isnull().all().all():
                            errors.append("At least one row with valid data is required.")
                        else:
                            for idx, row in edited_df.iterrows():
                                if pd.isna(row['Block']) or row['Block'] == '':
                                    errors.append(f"Row {idx+1}: Block is required.")
                                if pd.isna(row['Approved Activity']) or row['Approved Activity'] == '':
                                    errors.append(f"Row {idx+1}: Approved Activity is required.")
                                if row['Desired Target'] < 1:
                                    errors.append(f"Row {idx+1}: Desired Target must be at least 1.")
                                if row['Expected Persondays'] < 1:
                                    errors.append(f"Row {idx+1}: Expected Persondays must be at least 1.")
                        if errors:
                            for err in errors:
                                st.error(f"⚠️ {err}")
                        else:
                            # Delete existing targets
                            q_del = supabase.table("department_targets").delete() \
                                .eq("department_id", active_dept_id) \
                                .eq("district_id", dist_id) \
                                .eq("financial_year_id", selected_fy_target_id)
                            if active_wing_id:
                                q_del = q_del.eq("wing_id", active_wing_id)
                            else:
                                q_del = q_del.is_("wing_id", "null")
                            try:
                                q_del.execute()
                            except Exception as e:
                                st.warning(f"Could not delete old targets: {e}")

                            # Insert new targets
                            inserted = 0
                            for idx, row in edited_df.iterrows():
                                if pd.isna(row['Block']) or row['Block'] == '':
                                    continue
                                block_id = block_options.get(row['Block'])
                                if not block_id:
                                    continue
                                act_name = row['Approved Activity']
                                if not act_name:
                                    continue
                                target_record = {
                                    "department_id": active_dept_id,
                                    "wing_id": active_wing_id,
                                    "district_id": dist_id,
                                    "block_id": block_id,
                                    "financial_year_id": selected_fy_target_id,
                                    "financial_year": selected_fy_year,
                                    "project_head": selected_theme_name,
                                    "activity": act_name,
                                    "asset_count": 0,
                                    "annual_plan_scope": annual_plan_scope,
                                    "desired_target": int(row['Desired Target']),
                                    "department_fund": float(row['Dept Fund (₹ Lakhs)']),
                                    "vbgramg_fund": float(row['VB-G Fund (₹ Lakhs)']),
                                    "expected_persondays": int(row['Expected Persondays']),
                                    "created_by": user['id'],
                                    "department_scheme_convergence": conv_choice == "Yes",
                                    "department_scheme_name": scheme_name.strip() if scheme_name else None,
                                    "department_annual_plan_status": annual_plan_status,
                                    "department_scheme_remarks": None,  # Removed – always NULL
                                }
                                try:
                                    supabase.table("department_targets").insert(target_record).execute()
                                    inserted += 1
                                except Exception as e:
                                    st.error(f"Error inserting row {idx+1}: {e}")
                            if inserted > 0:
                                st.success(f"✅ {inserted} target(s) saved successfully!")
                                st.rerun()
                            else:
                                st.warning("No new targets were inserted.")

        with col_t1:
            st.markdown("#### 📊 Target Analytics Dashboard")
            if not df_t.empty:
                def format_dept_display(row):
                    d_name = dept_map.get(row.get('department_id'), 'Unknown')
                    w_id = row.get('wing_id')
                    if w_id and not pd.isna(w_id) and w_id in wing_map:
                        return f"{d_name} ➔ {wing_map[w_id]['wing_name']}"
                    return f"{d_name} (Main)"
                df_t['Department / Wing'] = df_t.apply(format_dept_display, axis=1)
                if 'project_head' not in df_t.columns:
                    df_t['project_head'] = "N/A"
                if 'block_id' in df_t.columns:
                    df_t['Block'] = df_t['block_id'].map(block_map).fillna('All Blocks')
                df_t.rename(columns={
                    'project_head': 'Project Head',
                    'activity': 'Approved Activity',
                    'desired_target': 'Target',
                    'department_fund': 'Dept. Fund',
                    'vbgramg_fund': 'VB-G Fund',
                    'expected_persondays': 'Persondays'
                }, inplace=True)
                if 'department_scheme_convergence' in df_t.columns:
                    df_t['Own Scheme Conv.'] = df_t['department_scheme_convergence'].map({True: 'Yes', False: 'No'})
                if 'department_scheme_name' in df_t.columns:
                    df_t['Scheme / Fund Name'] = df_t['department_scheme_name']
                if 'department_annual_plan_status' in df_t.columns:
                    df_t['Own Annual Plan Status'] = df_t['department_annual_plan_status']
                if 'department_scheme_remarks' in df_t.columns:
                    df_t['Remarks'] = df_t['department_scheme_remarks']
                disp_cols = ['Department / Wing', 'Project Head', 'Approved Activity', 'Target', 'Dept. Fund', 'VB-G Fund', 'Persondays']
                if 'Block' in df_t.columns:
                    disp_cols.insert(1, 'Block')
                extra_cols = [c for c in ['Own Scheme Conv.', 'Scheme / Fund Name', 'Own Annual Plan Status', 'Remarks'] if c in df_t.columns]
                disp_cols.extend(extra_cols)
                st.dataframe(df_t[disp_cols], use_container_width=True, hide_index=True)
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_t[disp_cols].to_excel(writer, index=False, sheet_name='Targets')
                st.download_button(
                    "📥 Export Target Plan to Excel",
                    data=buffer.getvalue(),
                    file_name="department_targets.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("No targets mapped for your jurisdiction. Use the form to plan annual targets.")
    # ================= TAB 2 =================
    with tab2:
        st.markdown("#### 🏗️ Execution & Progress Controller")
        query_reg = supabase.table("convergence_register").select("*")
        if role == 'district':
            query_reg = query_reg.eq("district_id", user['district_id'])
        elif role == 'block':
            query_reg = query_reg.eq("block_id", user['block_id'])
        elif role == 'department':
            query_reg = query_reg.eq("department_id", user['department_id']).eq("district_id", user['district_id'])
        activities_reg = query_reg.execute().data
        if not activities_reg:
            st.info("No convergence activities found in the register to monitor.")
        else:
            col_dept, col_wing, col_block, col_gp = st.columns(4)
            dept_options_all = [{"id": d['id'], "name": d['department_name']} for d in departments]
            dept_names = ["All"] + [d['name'] for d in dept_options_all]
            dept_id_map = {d['name']: d['id'] for d in dept_options_all}
            dept_frozen = (role == 'department')
            if dept_frozen:
                default_dept_name = dept_map.get(user.get('department_id'), '')
                sel_dept_name = col_dept.selectbox("Department", [default_dept_name] if default_dept_name else ["All"], disabled=True)
                sel_dept_id = user.get('department_id')
            else:
                sel_dept_name = col_dept.selectbox("Department", dept_names)
                sel_dept_id = dept_id_map.get(sel_dept_name) if sel_dept_name != "All" else None
            if sel_dept_id:
                dept_wings = dept_to_wings.get(sel_dept_id, [])
                wing_names = ["All"] + [w['wing_name'] for w in dept_wings]
            else:
                wing_names = ["All"]
            if dept_frozen:
                default_wing_name = wing_map.get(user.get('wing_id'), {}).get('wing_name', '') if user.get('wing_id') else ''
                if default_wing_name and default_wing_name in wing_names:
                    wing_options = [default_wing_name]
                else:
                    wing_options = ["All"]
                sel_wing_name = col_wing.selectbox("Wing", wing_options, disabled=True)
                sel_wing_id = user.get('wing_id') if default_wing_name in wing_names else None
            else:
                sel_wing_name = col_wing.selectbox("Wing", wing_names)
                if sel_wing_name != "All" and sel_dept_id:
                    wing_obj = next((w for w in dept_wings if w['wing_name'] == sel_wing_name), None)
                    sel_wing_id = wing_obj['id'] if wing_obj else None
                else:
                    sel_wing_id = None

            if role in ['district', 'block', 'department'] and user.get('district_id'):
                district_blocks = [b for b in blocks if b['district_id'] == user['district_id']]
            else:
                district_blocks = blocks
            block_names_all = ["All"] + sorted([b['block_name'] for b in district_blocks])
            block_id_from_name = {b['block_name']: b['id'] for b in district_blocks}
            if role == 'block':
                user_block_name = block_map.get(user.get('block_id'), '')
                if user_block_name and user_block_name in block_names_all:
                    block_options = [user_block_name]
                else:
                    block_options = ["All"]
                selected_block_name = col_block.selectbox("Block", block_options, disabled=True)
                selected_block_id = user.get('block_id')
            else:
                selected_block_name = col_block.selectbox("Block", block_names_all)
                selected_block_id = block_id_from_name.get(selected_block_name) if selected_block_name != "All" else None

            gp_options = ["All"]
            if selected_block_id:
                block_key = selected_block_name.upper()
                gp_options.extend(HOOGHLY_GPS.get(block_key, []))
            else:
                all_gps = set()
                for a in activities_reg:
                    loc = a.get('geo_location', '')
                    if 'GP:' in loc:
                        gp_part = loc.split('GP:')[1].split('|')[0].strip()
                        if gp_part:
                            all_gps.add(gp_part)
                gp_options.extend(sorted(all_gps))
            selected_gp = col_gp.selectbox("Primary GP", gp_options)

            filtered_activities = activities_reg
            if sel_dept_id:
                filtered_activities = [a for a in filtered_activities if a.get('department_id') == sel_dept_id]
            if sel_wing_id:
                filtered_activities = [a for a in filtered_activities if a.get('wing_id') == sel_wing_id]
            if selected_block_id:
                filtered_activities = [a for a in filtered_activities if a.get('block_id') == selected_block_id]
            if selected_gp != "All":
                filtered_activities = [a for a in filtered_activities if selected_gp in a.get('geo_location', '')]

            if not filtered_activities:
                st.warning("No activities match the selected filters.")
            else:
                activity_map = {a['id']: f"[{a.get('current_status', 'Planned').upper()}] {a.get('activity_description', 'Unnamed Activity')}" for a in filtered_activities}
                selected_act_id = st.selectbox("🔍 Search & Select Specific Work to Update", options=list(activity_map.keys()), format_func=lambda x: activity_map[x])
                selected_act = next((a for a in filtered_activities if a['id'] == selected_act_id), None)

                if selected_act:
                    dept_name = dept_map.get(selected_act.get('department_id'), 'N/A')
                    wing_id = selected_act.get('wing_id')
                    wing_name = wing_map.get(wing_id, {}).get('wing_name', 'Direct Parent Dept.') if wing_id else 'Direct Parent Dept.'
                    st.markdown(f"""
                    <div style="background:#F8FAFC; padding:16px; border-radius:8px; border:1px solid #E2E8F0; margin-bottom: 20px;">
                        <div style="color:#0F4C81; font-weight:700; font-size:16px; margin-bottom:8px;">{selected_act.get('activity_description')}</div>
                        <div style="display:flex; flex-wrap:wrap; gap:20px; font-size:13px; color:#475569;">
                            <div><b>Department:</b> {dept_name}</div>
                            <div><b>Wing:</b> {wing_name}</div>
                            <div><b>Source:</b> {selected_act.get('origin_source', 'N/A')}</div>
                            <div><b>Type:</b> {selected_act.get('convergence_type', 'N/A')}</div>
                            <div><b>PIA:</b> {selected_act.get('pia_type', 'Not Assigned')}</div>
                            <div><b>Location:</b> {selected_act.get('geo_location', 'N/A')}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    col_p_left, col_p_right = st.columns([1.5, 1], gap="large")
                    with col_p_left:
                        st.markdown("##### 📝 Update Progress Status")

                        # Clickable MIS Link
                        st.markdown(
                            """
                            <div style="margin-bottom: 10px;">
                                <a href="https://vbgramgrep.dord.gov.in/VBGRAMG/MISreport.aspx" target="_blank" style="color: #0F4C81; font-weight: 500; text-decoration: none; border-bottom: 1px dashed #0F4C81;">
                                    🔗 VB GRAMG Soft
                                </a>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        with st.form("update_progress_form"):
                            col_status, col_mis = st.columns(2)
                            status_options = [
                                "Planned",
                                "Approved",
                                "Ongoing",
                                "Suspended",
                                "Completed",
                                "Physically Completed",
                                "Deleted",
                                "Delayed",
                                "Dropped"
                            ]
                            current_status = selected_act.get('current_status', 'Planned')
                            status_mapping = {
                                "Under Implementation": "Ongoing",
                                "Approved": "Approved",
                                "Completed": "Completed",
                                "Delayed": "Delayed",
                                "Dropped": "Dropped"
                            }
                            if current_status in status_mapping:
                                current_status = status_mapping[current_status]
                            if current_status not in status_options:
                                current_status = "Planned"
                            default_index = status_options.index(current_status) if current_status in status_options else 0
                            new_status = col_status.selectbox("New Status*", status_options, index=default_index)

                            mis_code_val = col_mis.text_input(
                                "MIS Code (Mandatory if Active/Done)",
                                value=selected_act.get('mis_code', '') or '',
                                placeholder="e.g. 3206002005/FP/VB/320201060600000"
                            )

                            col_pia, col_conv = st.columns(2)
                            is_editable = role in ['superadmin', 'district']
                            curr_pia = selected_act.get("pia_type", "Select PIA")
                            pia_index = PIA_OPTIONS.index(curr_pia) if curr_pia in PIA_OPTIONS else 0
                            pia_type_sel = col_pia.selectbox(
                                "Implementing Agency (PIA)*",
                                PIA_OPTIONS,
                                index=pia_index,
                                disabled=not is_editable
                            )

                            curr_conv = selected_act.get("convergence_type", CONVERGENCE_TYPES[0])
                            conv_index = CONVERGENCE_TYPES.index(curr_conv) if curr_conv in CONVERGENCE_TYPES else 0
                            new_conv_type = col_conv.selectbox(
                                "Type of Convergence*",
                                CONVERGENCE_TYPES,
                                index=conv_index,
                                disabled=not is_editable
                            )

                            phys_ach = st.slider(
                                "Physical Achievement (%)*",
                                min_value=0, max_value=100,
                                value=int(float(selected_act.get('physical_achievement', 0.0) or 0.0))
                            )

                            st.markdown("##### 💰 Financials & MIS Registration")
                            col_p3, col_p4 = st.columns(2)
                            fin_ach = col_p3.number_input(
                                "Financial Achievement (₹ Lakhs)",
                                min_value=0.0,
                                value=float(selected_act.get('financial_achievement', 0.0) or 0.0)
                            )

                            col_s1, col_s2, col_s3 = st.columns(3)
                            sanction_wages = col_s1.number_input(
                                "Sanction Wages (₹)",
                                min_value=0,
                                value=int(selected_act.get('sanction_wages', 0) or 0),
                                step=1000
                            )
                            sanction_material = col_s2.number_input(
                                "Sanction Material (₹)",
                                min_value=0,
                                value=int(selected_act.get('sanction_material', 0) or 0),
                                step=1000
                            )
                            total_sanction = sanction_wages + sanction_material
                            col_s3.text_input("Total Sanction (₹)", value=f"{total_sanction:,}", disabled=True)

                            col_mandays, col_persondays = st.columns(2)
                            current_fy_mandays = col_mandays.number_input(
                                "Mandays Generated (Current FY)",
                                min_value=0,
                                value=int(selected_act.get('current_fy_mandays', 0) or 0)
                            )
                            persondays_gen = col_persondays.number_input(
                                "Persondays Generated (Cumulative)",
                                min_value=0,
                                value=int(selected_act.get('persondays_generated', 0) or 0)
                            )

                            st.markdown("##### 📅 Schedule & Blockages")
                            col_p5, col_p6, col_p7 = st.columns(3)
                            start_date = col_p5.date_input(
                                "Actual Start",
                                value=safe_parse_date(selected_act.get('actual_start_date'))
                            )
                            exp_date = col_p6.date_input(
                                "Expected End",
                                value=safe_parse_date(selected_act.get('expected_completion_date'))
                            )
                            act_date = col_p7.date_input(
                                "Actual End",
                                value=safe_parse_date(selected_act.get('actual_completion_date'))
                            )

                            remarks = st.text_area(
                                "Remarks / Blockage Details",
                                value=selected_act.get('remarks', '') or ''
                            )

                            if st.form_submit_button("Commit Progress Update", type="primary", use_container_width=True):
                                mis_required = new_status not in ["Planned", "Delayed", "Dropped"]
                                if mis_required and not mis_code_val.strip():
                                    st.error("⚠️ **Validation Error:** MIS Code is mandatory for the selected status.")
                                elif pia_type_sel == "Select PIA":
                                    st.error("⚠️ **Validation Error:** PIA (Implementing Agency) is mandatory.")
                                elif new_conv_type not in CONVERGENCE_TYPES:
                                    st.error("⚠️ **Validation Error:** Valid Convergence Type required.")
                                else:
                                    update_data = {
                                        "current_status": new_status,
                                        "convergence_type": new_conv_type,
                                        "pia_type": pia_type_sel,
                                        "mis_code": mis_code_val.strip() if mis_code_val else None,
                                        "physical_achievement": phys_ach,
                                        "financial_achievement": fin_ach,
                                        "persondays_generated": persondays_gen,
                                        "sanction_wages": sanction_wages,
                                        "sanction_material": sanction_material,
                                        "current_fy_mandays": current_fy_mandays,
                                        "actual_start_date": str(start_date) if start_date else None,
                                        "expected_completion_date": str(exp_date) if exp_date else None,
                                        "actual_completion_date": str(act_date) if act_date else None,
                                        "remarks": remarks
                                    }
                                    try:
                                        resp = supabase.table("convergence_register").update(update_data).eq("id", selected_act_id).execute()
                                        if resp.count and resp.count > 0:
                                            history_payload = {
                                                "convergence_id": selected_act_id,
                                                "status": new_status,
                                                "physical_achievement": phys_ach,
                                                "financial_achievement": fin_ach,
                                                "persondays_generated": persondays_gen,
                                                "remarks": f"MIS: {mis_code_val} | {remarks}"
                                            }
                                            supabase.table("progress_updates").insert(history_payload).execute()
                                            try: log_action(user.get('id'), f"UPDATE convergence_register {selected_act_id}")
                                            except: pass
                                            st.success("✅ Progress updated successfully!")
                                            st.rerun()
                                        else:
                                            st.error("🔴 Update failed. Database security (RLS) prevented the update.")
                                    except Exception as e:
                                        st.error(f"Error saving progress: {e}")

                    with col_p_right:
                        st.markdown("#### ⏳ Activity Audit Timeline")
                        try:
                            history_query = supabase.table("progress_updates").select("*").eq("convergence_id", selected_act_id).order("created_at", desc=True).execute()
                            if history_query.data:
                                for idx, h in enumerate(history_query.data):
                                    h_date = pd.to_datetime(h['created_at']).strftime('%d %b %Y, %H:%M')
                                    st.markdown(f"""
                                    <div style="border-left: 2px solid #CBD5E1; padding-left: 15px; margin-bottom: 15px; margin-left: 5px;">
                                        <div style="font-size: 11px; color: #64748B;">{h_date}</div>
                                        <div style="font-weight: 600; color: #1E293B;">State changed to: {h.get('status')}</div>
                                        <div style="font-size: 13px; color: #475569;">Physical: {h.get('physical_achievement')}% | Financial: ₹{h.get('financial_achievement')}L</div>
                                    </div>
                                    """, unsafe_allow_html=True)
                            else:
                                st.info("No historical updates recorded for this activity yet.")
                        except Exception:
                            st.warning("Could not load history timeline.")

    # ================= TAB 3 =================
    with tab3:
        st.markdown("#### 🤝 Synchronized Departmental Meeting Commitments")
        st.caption("Live Feed: Real-time action points assigned from statutory committee meetings across District and Block jurisdictions.")
        ap_query = supabase.table("meeting_action_points").select("id, meeting_id, department_id, wing_id, priority, linkage_type, action_point, target, deadline, status, remarks").execute().data
        if ap_query:
            df_ap = pd.DataFrame(ap_query)
            if role == 'department':
                if user.get('wing_id'):
                    df_ap = df_ap[(df_ap['department_id'] == user['department_id']) & (df_ap['wing_id'] == user['wing_id'])]
                else:
                    df_ap = df_ap[(df_ap['department_id'] == user['department_id']) & (df_ap['wing_id'].isna())]
            if not df_ap.empty:
                def format_dept_display(row):
                    d_name = dept_map.get(row.get("department_id"), "Unknown")
                    w_id = row.get("wing_id")
                    if w_id and not pd.isna(w_id) and w_id in wing_map: return f"{d_name} ➔ {wing_map[w_id]['wing_name']}"
                    return f"{d_name} (Main)"
                df_ap['Department / Wing'] = df_ap.apply(format_dept_display, axis=1)
                
                meetings_data = supabase.table("meetings").select("id, meeting_date, meeting_type, district_id, block_id").execute().data or []
                m_map = {m['id']: m for m in meetings_data}
                
                def get_meeting_context(meeting_id):
                    if meeting_id not in m_map: return "Unknown Meeting"
                    m = m_map[meeting_id]
                    m_type = m.get('meeting_type', 'Other')
                    d_id = m.get('district_id')
                    b_id = m.get('block_id')
                    if m_type == 'District':
                        d_name = dist_map.get(d_id, 'Unknown District')
                        return f"District Meeting: {d_name}"
                    elif m_type == 'Block':
                        b_name = block_map.get(b_id, 'Unknown Block')
                        d_name = dist_map.get(d_id, 'Unknown District')
                        return f"Block Meeting: {b_name} ({d_name} District)"
                    return f"{m_type} Meeting"
                
                df_ap['Meeting Context'] = df_ap['meeting_id'].apply(get_meeting_context)

                pending_ap = df_ap[~df_ap['status'].isin(['Completed', 'Dropped', 'completed', 'dropped'])].copy()
                if not pending_ap.empty:
                    pending_ap['deadline'] = pd.to_datetime(pending_ap['deadline'], errors='coerce')
                    today_dt = pd.to_datetime(date.today())
                    pending_ap['Days Left'] = (pending_ap['deadline'] - today_dt).dt.days
                    def get_sla_badge(days):
                        if pd.isna(days): return "⚪ Unscheduled"
                        if days < 0: return "🔴 Overdue"
                        if days == 0: return "🟡 Due Today"
                        if days <= 3: return "🟠 Due Soon"
                        return "🔵 On Track"
                    pending_ap['SLA Status'] = pending_ap['Days Left'].apply(get_sla_badge)
                    sk1, sk2, sk3, sk4 = st.columns(4)
                    sk1.metric("Open Assigned", len(pending_ap))
                    sk2.metric("Overdue / Breach", len(pending_ap[pending_ap['Days Left'] < 0]))
                    sk3.metric("Due Today", len(pending_ap[pending_ap['Days Left'] == 0]))
                    sk4.metric("Requires Review", len(pending_ap[pending_ap['status'].str.contains('Feasible|Review', case=False, na=False)]))
                    st.markdown("<br>##### 📑 Live Action Registry", unsafe_allow_html=True)
                    disp_cols = ['SLA Status', 'Meeting Context', 'Department / Wing', 'action_point', 'Days Left', 'status']
                    st.dataframe(pending_ap[disp_cols].sort_values('Days Left'), use_container_width=True, hide_index=True)
                    st.markdown("##### ✏️ Update ATR Status & Progress")
                    with st.form("sync_atr_form"):
                        col_s1, col_s2 = st.columns(2)
                        sync_id = col_s1.selectbox("Select Resolution", pending_ap['id'].tolist(), format_func=lambda x: f"[{pending_ap[pending_ap['id']==x]['Meeting Context'].values[0]}] {pending_ap[pending_ap['id']==x]['action_point'].values[0][:50]}...")
                        sync_status = col_s2.selectbox("New Status*", ['Under Process', 'Approved', 'Under Execution', 'Completed', 'Not Feasible (Requires Review)', 'Dropped'])
                        sync_remarks = st.text_area("Implementation Outcome / Remarks (Mandatory if 'Not Feasible')")
                        submitted_sync = st.form_submit_button("Sync Progress to Master Record", type="primary")
                        if submitted_sync:
                            if sync_status == 'Not Feasible (Requires Review)' and not sync_remarks.strip():
                                st.error("⚠️ **Validation Error:** You must provide a clear reason in 'Remarks' when flagging an activity as Not Feasible so the Chairperson can review it.")
                            else:
                                payload = {"status": sync_status, "remarks": sync_remarks}
                                resp = supabase.table("meeting_action_points").update(payload).eq("id", sync_id).execute()
                                if resp.count and resp.count > 0:
                                    try: log_action(user.get('id'), f"UPDATE meeting_action_points {sync_id}")
                                    except: pass
                                    st.success("✅ Master meeting record updated instantly across all dashboards!")
                                    st.rerun()
                                else:
                                    st.error("🔴 Update blocked by database security (RLS).")
            else:
                st.info("No meeting commitments found for your department jurisdiction.")
        else:
            st.info("No resolution records found in the global governance system.")

    # ================= TAB 4 =================
    with tab4:
        st.markdown("#### 🚨 Departmental Target Compliance Tracker")

        q_t = supabase.table("department_targets").select("*")
        q_r = supabase.table("convergence_register").select("*")

        if role == 'district' and user.get('district_id'):
            q_t = q_t.eq("district_id", user['district_id'])
            q_r = q_r.eq("district_id", user['district_id'])
        elif role == 'block':
            if user.get('district_id'): q_t = q_t.eq("district_id", user['district_id'])
            if user.get('block_id'): 
                q_r = q_r.eq("block_id", user['block_id'])
                q_t = q_t.eq("block_id", user['block_id'])
        elif role == 'department':
            if user.get('department_id'):
                q_t = q_t.eq("department_id", user['department_id'])
                q_r = q_r.eq("department_id", user['department_id'])
            if user.get('district_id'):
                q_t = q_t.eq("district_id", user['district_id'])
                q_r = q_r.eq("district_id", user['district_id'])

        df_tab4_tgts = pd.DataFrame(q_t.execute().data or [])
        df_tab4_reg = pd.DataFrame(q_r.execute().data or [])

        if not df_tab4_tgts.empty:
            if 'financial_year_id' in df_tab4_tgts.columns and active_fy_id is not None:
                df_tab4_tgts = df_tab4_tgts[df_tab4_tgts['financial_year_id'] == active_fy_id]
            elif 'financial_year' in df_tab4_tgts.columns:
                df_tab4_tgts = df_tab4_tgts[df_tab4_tgts['financial_year'] == active_fy]
            if 'desired_target' in df_tab4_tgts.columns:
                df_tab4_tgts['desired_target'] = pd.to_numeric(df_tab4_tgts['desired_target'], errors='coerce').fillna(0)

        if not df_tab4_reg.empty:
            if 'financial_year_id' in df_tab4_reg.columns and active_fy_id is not None:
                df_tab4_reg = df_tab4_reg[df_tab4_reg['financial_year_id'] == active_fy_id]
            elif 'financial_year' in df_tab4_reg.columns:
                df_tab4_reg = df_tab4_reg[df_tab4_reg['financial_year'] == active_fy]

        compliance_data = []
        if not df_tab4_tgts.empty:
            for _, row in df_tab4_tgts.iterrows():
                d_id = row['department_id']
                w_id = row.get('wing_id')
                b_id = row.get('block_id')
                target_val = safe_int(row.get('desired_target', 0))
                t_act = row.get('activity', '')

                target_w_id_safe = None if pd.isna(w_id) else w_id
                dept_name = dept_map.get(d_id, 'Unknown')
                wing_name = wing_map.get(target_w_id_safe, {}).get('wing_name', 'Main Dept.') if target_w_id_safe else 'Main Dept.'
                dept_display = f"{dept_name} → {wing_name}" if target_w_id_safe else dept_name
                block_name = block_map.get(b_id, 'All Blocks') if b_id else 'All Blocks'

                contacts = [u.get('full_name', 'Unknown') for u in users_data if u.get('department_id') == d_id and (None if pd.isna(u.get('wing_id')) else u.get('wing_id')) == target_w_id_safe]

                entered_count = 0
                if not df_tab4_reg.empty:
                    mask = (df_tab4_reg['department_id'] == d_id)
                    if b_id:
                        mask &= (df_tab4_reg['block_id'] == b_id)
                    if target_w_id_safe:
                        mask &= (df_tab4_reg['wing_id'] == target_w_id_safe)
                    else:
                        mask &= (df_tab4_reg['wing_id'].isna())
                    dept_reg = df_tab4_reg[mask]
                    if 'activity_description' in dept_reg.columns:
                        def is_match(work_desc):
                            work_lower = str(work_desc).lower()
                            target_words = set(re.findall(r'\w+', str(t_act).lower()))
                            work_words = set(re.findall(r'\w+', work_lower))
                            common = target_words.intersection(work_words)
                            return len(common) >= 3
                        entered_count = dept_reg['activity_description'].apply(is_match).sum()

                gap = entered_count - target_val
                status = "Less Entered (Needs Update)" if gap < 0 else "Extra Entered (Mismatch)" if gap > 0 else "Target Matched"
                compliance_data.append({
                    "Block": block_name,
                    "Department / Wing": dept_display, 
                    "Nodal Person": " | ".join(contacts) if contacts else "⚠️ No Login",
                    "Target Activity": t_act, 
                    "Target Set": target_val, 
                    "Entries Captured": entered_count, 
                    "Gap": gap, 
                    "Status": status
                })

        def style_compliance(row):
            if row['Status'] != "Target Matched":
                return ['background-color: #ffebee; color: #b71c1c; font-weight: bold;'] * len(row)
            return ['background-color: #e8f5e9; color: #1b5e20; font-weight: bold;'] * len(row)

        if compliance_data:
            df_comp = pd.DataFrame(compliance_data)
            col_f1, col_f2 = st.columns(2)
            blocks = sorted(df_comp['Block'].unique())
            sel_block = col_f1.selectbox("Filter by Block", options=["All"] + blocks)
            depts = sorted(df_comp['Department / Wing'].unique())
            sel_dept = col_f2.selectbox("Filter by Department / Wing", options=["All"] + depts)
            if sel_block != "All":
                df_comp = df_comp[df_comp['Block'] == sel_block]
            if sel_dept != "All":
                df_comp = df_comp[df_comp['Department / Wing'] == sel_dept]
            st.dataframe(df_comp.style.apply(style_compliance, axis=1), use_container_width=True, hide_index=True)
        else:
            st.info(f"No Departmental Targets have been set yet for FY {active_fy}.")

    # ================= NEW TAB 5: PROGRESS AUDIT TRAIL & HISTORY =================
    with tab5:
        st.markdown("#### 📋 Global Progress History")
        st.caption("View every single progress update across all schemes.")

        # 1. Fetch all Progress Updates with necessary joins
        try:
            # Assuming the database has these tables linked correctly
            audit_query = supabase.table("progress_updates").select(
                "*, convergence_register(id, activity_description, department_id, district_id, block_id), users(full_name, role, department_id, district_id, block_id)"
            ).order("created_at", desc=True)
            
            # 2. Restrict access if not Superadmin (Show only updates related to their jurisdiction)
            if role != 'superadmin':
                # Filter by department or district/block based on the logged-in user
                if role == 'department':
                    audit_query = audit_query.eq("convergence_register.department_id", user.get('department_id'))
                    if user.get('wing_id'):
                        audit_query = audit_query.eq("convergence_register.wing_id", user.get('wing_id'))
                elif role == 'district':
                    audit_query = audit_query.eq("convergence_register.district_id", user.get('district_id'))
                elif role == 'block':
                    audit_query = audit_query.eq("convergence_register.block_id", user.get('block_id'))

            audit_data = audit_query.execute().data or []

            if not audit_data:
                st.info("No progress history records found for your jurisdiction.")
            else:
                # 3. Transform Data for Display
                audit_rows = []
                for rec in audit_data:
                    # Extract convergence details
                    conv = rec.get('convergence_register') or {}
                    act_desc = conv.get('activity_description', 'Unknown Scheme/Work')
                    dept_id = conv.get('department_id')
                    dist_id = conv.get('district_id')
                    block_id = conv.get('block_id')
                    
                    # Extract user details
                    updater = rec.get('users') or {}
                    updater_name = updater.get('full_name', 'System')
                    updater_role = updater.get('role', 'Unknown')

                    # Map IDs to Names
                    dept_name = dept_map.get(dept_id, 'Unknown Dept')
                    dist_name = dist_map.get(dist_id, 'Unknown Dist')
                    block_name = block_map.get(block_id, 'N/A')

                    audit_rows.append({
                        "Date & Time": pd.to_datetime(rec['created_at']).strftime('%d %b %Y, %H:%M'),
                        "Updater (User)": updater_name,
                        "Updater Role": updater_role.capitalize(),
                        "Scheme / Work": act_desc,
                        "Department": dept_name,
                        "District": dist_name,
                        "Block": block_name,
                        "Changed Status": rec.get('status', 'N/A'),
                        "Physical Achiev. %": rec.get('physical_achievement', 0),
                        "Financial Achiev. (₹L)": rec.get('financial_achievement', 0.0),
                        "Persondays": rec.get('persondays_generated', 0),
                        "Remarks": rec.get('remarks', ''),
                        "Update ID": rec['id']  # Hidden ID for superadmin actions
                    })

                df_audit = pd.DataFrame(audit_rows)

                # 4. Search Functionality
                search_audit = st.text_input("🔍 Search Audit History", placeholder="Search by Scheme, User, Department, Status...")
                if search_audit:
                    mask = df_audit.apply(lambda row: row.astype(str).str.contains(search_audit, case=False, na=False).any(), axis=1)
                    df_audit = df_audit[mask]

                # 5. Show Table
                display_cols = ["Date & Time", "Updater (User)", "Updater Role", "Scheme / Work", "Department", "District", "Block", "Changed Status", "Physical Achiev. %", "Financial Achiev. (₹L)", "Persondays", "Remarks"]
                
                # If User is Superadmin, add an Action column for Deletion
                if role == 'superadmin':
                    display_cols.append("🗑️ Action")

                st.dataframe(
                    df_audit[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Physical Achiev. %": st.column_config.ProgressColumn("Physical Achiev. %", min_value=0, max_value=100, format="%.0f%%"),
                        "Financial Achiev. (₹L)": st.column_config.NumberColumn("Financial (₹L)", format="₹%.2f"),
                        "Updater Role": st.column_config.TextColumn("Role"),
                        "Changed Status": st.column_config.TextColumn("Status"),
                    }
                )

                # 6. Downloads
                col_dl_a1, col_dl_a2 = st.columns(2)
                audit_buffer = io.BytesIO()
                with pd.ExcelWriter(audit_buffer, engine='openpyxl') as writer:
                    df_audit.drop(columns=['Update ID', '🗑️ Action'], errors='ignore').to_excel(writer, index=False, sheet_name='Audit_Trail')
                col_dl_a1.download_button("📥 Download Audit Trail (Excel)", data=audit_buffer.getvalue(), file_name="progress_audit_trail.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                
                col_dl_a2.download_button("📥 Download Audit Trail (CSV)", data=df_audit.drop(columns=['Update ID', '🗑️ Action'], errors='ignore').to_csv(index=False).encode("utf-8"), file_name="progress_audit_trail.csv", mime="text/csv", use_container_width=True)

                # 7. SUPERADMIN DELETE ACTION (Only editable by superadmin)
                if role == 'superadmin':
                    st.markdown("---")
                    st.caption("🛠️ **Superadmin Tools:** Select a record below to permanently delete an erroneous progress update.")
                    record_ids = df_audit['Update ID'].tolist()
                    selected_delete_id = st.selectbox(
                        "Select Update ID to Delete (Filter via Search above first):", 
                        options=record_ids, 
                        format_func=lambda x: f"Delete Record ID: {x} (Date: {df_audit[df_audit['Update ID'] == x]['Date & Time'].values[0]})"
                    )
                    
                    if st.button("🗑️ Permanently Delete Selected Progress Log", type="secondary"):
                        try:
                            supabase.table("progress_updates").delete().eq("id", selected_delete_id).execute()
                            st.success(f"✅ Progress Update (ID: {selected_delete_id}) permanently deleted!")
                            st.rerun() # Reset the page, preventing duplicate deletion
                        except Exception as del_err:
                            st.error(f"❌ Failed to delete: {del_err}")

        except Exception as e:
            st.error(f"Could not load audit trail. Please ensure database tables and relationships are correctly configured. Error: {e}")
