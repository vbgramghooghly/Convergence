import streamlit as st
import pandas as pd
from datetime import datetime
import io
import re
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

CONVERGENCE_TYPES = [
    "Technical Convergence (Zero Fund/NOC)", "Financial (as PIA)", "Financial (as Non-PIA)"
]
PIA_OPTIONS = ["Select PIA", "GP", "Block", "Department", "Other"]

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
    if pd.isna(val) or val is None or val == '': return 0
    try: return int(float(val))
    except (ValueError, TypeError): return 0

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
    if pd.isna(date_val) or not date_val: return None
    try:
        if isinstance(date_val, str): return pd.to_datetime(date_val).date()
        return date_val
    except Exception: return None

def render_department_targets(user, role, supabase, maps, master_data):
    query_t = supabase.table("department_targets").select("*")
    if role == 'department':
        query_t = query_t.eq("department_id", user.get('department_id')).eq("district_id", user.get('district_id'))
        if user.get('wing_id'): query_t = query_t.eq("wing_id", user.get('wing_id'))
        else: query_t = query_t.is_("wing_id", "null")
    elif role in ['district', 'block']:
        query_t = query_t.eq("district_id", user.get('district_id'))
    df_t = pd.DataFrame(query_t.execute().data or [])
    
    total_schemes = int(df_t['desired_target'].sum()) if not df_t.empty and 'desired_target' in df_t.columns else 0
    if not df_t.empty:
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total Schemes Targeted", total_schemes)
        k2.metric("Unique Projects", df_t['project_head'].nunique() if 'project_head' in df_t else 0)
        k3.metric("Unique Activities", df_t['activity'].nunique() if 'activity' in df_t else 0)
        k4.metric("Dept Fund (₹L)", f"₹{pd.to_numeric(df_t['department_fund'], errors='coerce').sum():,.2f}")
        k5.metric("Persondays Planned", f"{int(pd.to_numeric(df_t['expected_persondays'], errors='coerce').sum()):,}")
        st.markdown("<br>", unsafe_allow_html=True)

    col_t1, col_t2 = st.columns([1.6, 1], gap="large")
    with col_t1:
        st.markdown("#### 📊 Target Analytics Dashboard")
        if not df_t.empty:
            def format_dept_display(row):
                d_name = maps['dept_map'].get(row.get('department_id'), 'Unknown')
                w_id = row.get('wing_id')
                return f"{d_name} ➔ {maps['wing_map'][w_id]['wing_name']}" if w_id and not pd.isna(w_id) and w_id in maps['wing_map'] else f"{d_name} (Main)"
            df_t['Department / Wing'] = df_t.apply(format_dept_display, axis=1)
            if 'block_id' in df_t.columns: df_t['Block'] = df_t['block_id'].map(maps['block_map']).fillna('All Blocks')
            df_t.rename(columns={'project_head': 'Project Head', 'activity': 'Approved Activity', 'desired_target': 'Target', 'department_fund': 'Dept. Fund', 'vbgramg_fund': 'VB-G Fund', 'expected_persondays': 'Persondays'}, inplace=True)
            disp_cols = ['Department / Wing', 'Project Head', 'Approved Activity', 'Target', 'Dept. Fund', 'VB-G Fund', 'Persondays']
            if 'Block' in df_t.columns: disp_cols.insert(1, 'Block')
            st.dataframe(df_t[disp_cols], use_container_width=True, hide_index=True)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_t[disp_cols].to_excel(writer, index=False, sheet_name='Targets')
            st.download_button("📥 Export Target Plan", data=buffer.getvalue(), file_name="department_targets.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else: st.info("No targets mapped for your jurisdiction.")

    with col_t2:
        st.markdown("#### 📝 Add/Update Targets")
        if role == 'block': st.info("Target setting managed at District/Department level.")
        else:
            with st.container(border=True):
                fy_id_map = {f["id"]: f["year_name"].strip() for f in master_data["fys"]}
                fy_id = st.selectbox("Financial Year*", list(fy_id_map.keys()), format_func=lambda x: fy_id_map[x])
                dept_options = [{"label": f"{d['department_name']} (Main)", "dept_id": d['id'], "wing_id": None} for d in master_data["depts"]]
                for w in master_data["wings"]: dept_options.append({"label": f"{maps['dept_map'].get(w['department_id'], 'Unknown')} ➔ {w['wing_name']}", "dept_id": w['department_id'], "wing_id": w['id']})
                dept_options = sorted(dept_options, key=lambda x: x['label'])
                
                active_dept_id, active_wing_id, dist_id = user.get('department_id'), user.get('wing_id'), user.get('district_id')
                if role != 'department':
                    sel_dept_label = st.selectbox("Department / Wing*", [opt['label'] for opt in dept_options])
                    selected_opt = next(opt for opt in dept_options if opt['label'] == sel_dept_label)
                    active_dept_id, active_wing_id = selected_opt['dept_id'], selected_opt['wing_id']
                    dist_sel = st.selectbox("District*", list(maps['dist_map'].keys()) if maps['dist_map'] else ["None"])
                    dist_id = maps['dist_map'].get(dist_sel)

                st.markdown("---")
                project_head_options = ["Canals, Check Dams & Dykes", "Ponds & Water Harvesting", "Wells & Micro-Irrigation", "Waterlogged Land Reclamation", "Afforestation & Plantations", "Rooftop Rainwater Harvesting", "Rural Roads & Culverts", "GP Bhawans & Public Buildings", "School Infrastructure & Playgrounds", "Crematoria & Graveyards", "Solid & Liquid Waste Management", "Solar & Renewable Energy", "Parking, Sheds & Amenities", "Rural Housing (PMAY-G)", "Jal Jeevan Mission Maintenance", "Skill Centres & Work Sheds", "Rural Haats & Markets", "Agri-Storage & Cold Chains", "SHG & Federation Buildings", "Compost Structures", "Livestock Shelters & Dairy", "Fisheries & Aquaculture", "Nurseries & Building Materials", "Circular Economy Processing Units", "Disaster & Cyclone Shelters", "Embankments & Mitigation Works", "Post-Disaster Restoration"]
                valid_act_ids = [m['activity_id'] for m in master_data["act_dept_mapping"] if m['department_id'] == active_dept_id]
                valid_activities = [a for a in master_data["activities"] if a['id'] in valid_act_ids]
                act_names = [a['activity_name'] for a in valid_activities]

                dist_blocks = [b for b in master_data["blocks"] if b['district_id'] == dist_id]
                block_names = [b['block_name'] for b in dist_blocks] if dist_blocks else []
                init_df = pd.DataFrame({"Block": [""], "Project Head": [""], "Approved Activity": [""], "Desired Target": [1], "Dept Fund": [0.0], "VB-G Fund": [0.0], "Persondays": [0]})
                edited_df = st.data_editor(init_df, use_container_width=True, num_rows="dynamic", height=450, column_config={
                    "Block": st.column_config.SelectboxColumn("Block*", options=block_names, required=True),
                    "Project Head": st.column_config.SelectboxColumn("Project Head*", options=project_head_options, required=True),
                    "Approved Activity": st.column_config.SelectboxColumn("Activity*", options=act_names, required=True),
                    "Desired Target": st.column_config.NumberColumn("Target", min_value=0, step=1, required=True),
                    "Persondays": st.column_config.NumberColumn("Persondays*", min_value=0, step=1, required=True)
                })
                if st.button("💾 Save Targets", type="primary", use_container_width=True):
                    errors = []
                    if not active_dept_id or not dist_id: errors.append("Invalid Department/District.")
                    if edited_df.empty or edited_df.isnull().all().all(): errors.append("At least one valid row required.")
                    else:
                        for idx, row in edited_df.iterrows():
                            if pd.isna(row['Block']) or row['Block'] == '': errors.append(f"Row {idx+1}: Block required.")
                            if row['Desired Target'] < 1: errors.append(f"Row {idx+1}: Target must be >= 1.")
                            if row['Persondays'] < 1: errors.append(f"Row {idx+1}: Persondays must be >= 1.")
                    if errors:
                        for err in errors: st.error(f"⚠️ {err}")
                    else:
                        supabase.table("department_targets").delete().eq("department_id", active_dept_id).eq("district_id", dist_id).eq("financial_year_id", fy_id).execute()
                        for _, row in edited_df.iterrows():
                            if not row['Block']: continue
                            supabase.table("department_targets").insert({
                                "department_id": active_dept_id, "wing_id": active_wing_id, "district_id": dist_id,
                                "block_id": maps['block_map'][row['Block']], "financial_year_id": fy_id, "financial_year": fy_id_map[fy_id],
                                "project_head": row['Project Head'], "activity": row['Approved Activity'],
                                "desired_target": int(row['Desired Target']), "department_fund": float(row['Dept Fund']),
                                "vbgramg_fund": float(row['VB-G Fund']), "expected_persondays": int(row['Persondays']),
                                "created_by": user['id']
                            }).execute()
                        st.success("✅ Targets saved!")
                        st.rerun()

def render_implementation_progress(user, role, supabase, maps, master_data):
    query_reg = supabase.table("convergence_register").select("*")
    if role == 'district': query_reg = query_reg.eq("district_id", user['district_id'])
    elif role == 'block': query_reg = query_reg.eq("block_id", user['block_id'])
    elif role == 'department': query_reg = query_reg.eq("department_id", user['department_id']).eq("district_id", user['district_id'])
    activities = query_reg.execute().data
    if not activities: st.info("No convergence activities found."); return

    col_dept, col_wing, col_block, col_gp = st.columns(4)
    dept_names = ["All"] + [d['department_name'] for d in master_data["depts"]]
    sel_dept_name = col_dept.selectbox("Department", dept_names)
    sel_dept_id = {d['department_name']: d['id'] for d in master_data["depts"]}.get(sel_dept_name) if sel_dept_name != "All" else None
    wing_names = ["All"] + [w['wing_name'] for w in maps['dept_to_wings'].get(sel_dept_id, [])] if sel_dept_id else ["All"]
    sel_wing_name = col_wing.selectbox("Wing", wing_names)
    sel_wing_id = next((w['id'] for w in maps['dept_to_wings'].get(sel_dept_id, []) if w['wing_name'] == sel_wing_name), None) if sel_wing_name != "All" else None

    district_blocks = [b for b in master_data["blocks"] if b['district_id'] == user.get('district_id')]
    block_names = ["All"] + sorted([b['block_name'] for b in district_blocks])
    sel_block_name = col_block.selectbox("Block", block_names)
    sel_block_id = {b['block_name']: b['id'] for b in district_blocks}.get(sel_block_name) if sel_block_name != "All" else None
    
    gp_options = ["All"]
    if sel_block_id: gp_options.extend(HOOGHLY_GPS.get(sel_block_name.upper(), []))
    else:
        gps = set()
        for a in activities:
            loc = a.get('geo_location', '')
            if 'GP:' in loc: 
                gp_part = loc.split('GP:')[1].split('|')[0].strip()
                if gp_part: gps.add(gp_part)
        gp_options.extend(sorted(gps))
    sel_gp = col_gp.selectbox("GP", gp_options)

    filtered = [a for a in activities if (not sel_dept_id or a.get('department_id') == sel_dept_id) and (not sel_wing_id or a.get('wing_id') == sel_wing_id) and (not sel_block_id or a.get('block_id') == sel_block_id) and (sel_gp == "All" or sel_gp in a.get('geo_location', ''))]
    if not filtered: st.warning("No matching activities."); return

    act_map = {a['id']: f"[{a.get('current_status', 'Planned').upper()}] {a.get('activity_description')}" for a in filtered}
    sel_id = st.selectbox("🔍 Select Work to Update", list(act_map.keys()), format_func=lambda x: act_map[x])
    rec = next((a for a in filtered if a['id'] == sel_id), None)
    if not rec: return

    st.markdown(f"""<div style="background:#F8FAFC; padding:16px; border-radius:8px; border:1px solid #E2E8F0;"><b>{rec.get('activity_description')}</b><br>Department: {maps['dept_map'].get(rec.get('department_id'), 'N/A')} | PIA: {rec.get('pia_type')}</div>""", unsafe_allow_html=True)
    col_left, col_right = st.columns([1.5, 1])
    with col_left:
        with st.form("progress_form"):
            status_opts = ["Planned", "Approved", "Ongoing", "Suspended", "Completed", "Physically Completed", "Deleted", "Delayed", "Dropped"]
            curr = {"Under Implementation": "Ongoing", "Approved": "Approved", "Completed": "Completed", "Delayed": "Delayed", "Dropped": "Dropped"}.get(rec.get('current_status'), "Planned")
            new_status = st.selectbox("New Status*", status_opts, index=status_opts.index(curr) if curr in status_opts else 0)
            mis_code = st.text_input("MIS Code (Mandatory if active)", value=rec.get('mis_code', '') or '')
            phys_ach = st.slider("Physical Achievement (%)", 0, 100, int(float(rec.get('physical_achievement', 0.0) or 0.0)))
            fin_ach = st.number_input("Financial Achievement (₹ Lakhs)", 0.0, value=float(rec.get('financial_achievement', 0.0) or 0.0))
            pdays_gen = st.number_input("Persondays Generated", 0, value=int(rec.get('persondays_generated', 0) or 0))
            start = st.date_input("Actual Start", value=safe_parse_date(rec.get('actual_start_date')))
            exp = st.date_input("Expected End", value=safe_parse_date(rec.get('expected_completion_date')))
            remarks = st.text_area("Remarks", value=rec.get('remarks', '') or '')

            if st.form_submit_button("Commit Progress", type="primary", use_container_width=True):
                if new_status not in ["Planned", "Delayed", "Dropped"] and not mis_code.strip(): st.error("MIS Code mandatory for selected status.")
                else:
                    update_data = {"current_status": new_status, "mis_code": mis_code.strip() or None, "physical_achievement": phys_ach, "financial_achievement": fin_ach, "persondays_generated": pdays_gen, "actual_start_date": str(start) if start else None, "expected_completion_date": str(exp) if exp else None, "remarks": remarks}
                    supabase.table("convergence_register").update(update_data).eq("id", sel_id).execute()
                    supabase.table("progress_updates").insert({"convergence_id": sel_id, "status": new_status, "physical_achievement": phys_ach, "financial_achievement": fin_ach, "persondays_generated": pdays_gen, "remarks": f"MIS: {mis_code} | {remarks}"}).execute()
                    st.success("✅ Progress updated!"); st.rerun()

    with col_right:
        st.markdown("#### ⏳ Audit Timeline")
        hist = supabase.table("progress_updates").select("*").eq("convergence_id", sel_id).order("created_at", desc=True).execute().data
        if hist:
            for h in hist:
                d = pd.to_datetime(h['created_at']).strftime('%d %b %Y, %H:%M')
                st.markdown(f"<div style='border-left:2px solid #CBD5E1; padding-left:15px; margin:10px 0;'><b>{d}</b><br>Status: {h.get('status')} | Physical: {h.get('physical_achievement')}%</div>", unsafe_allow_html=True)
        else: st.info("No history recorded.")

def render_target_compliance(user, role, supabase, maps, master_data, active_fy_id, active_fy):
    q_t = supabase.table("department_targets").select("*")
    q_r = supabase.table("convergence_register").select("*")
    if role == 'district': q_t = q_t.eq("district_id", user['district_id']); q_r = q_r.eq("district_id", user['district_id'])
    elif role == 'block': q_t = q_t.eq("block_id", user['block_id']); q_r = q_r.eq("block_id", user['block_id'])
    elif role == 'department': q_t = q_t.eq("department_id", user['department_id']); q_r = q_r.eq("department_id", user['department_id'])
    df_tgts = pd.DataFrame(q_t.execute().data or [])
    df_reg = pd.DataFrame(q_r.execute().data or [])
    if active_fy_id:
        df_tgts = df_tgts[df_tgts.get('financial_year_id') == active_fy_id] if 'financial_year_id' in df_tgts else df_tgts[df_tgts.get('financial_year') == active_fy]
        df_reg = df_reg[df_reg.get('financial_year_id') == active_fy_id] if 'financial_year_id' in df_reg else df_reg[df_reg.get('financial_year') == active_fy]

    act_id_to_name = {a['id']: a['activity_name'] for a in master_data['activities']}
    if not df_reg.empty:
        def get_match(row): 
            theme = row.get('thematic_category_id')
            if theme and theme in act_id_to_name: return act_id_to_name[theme].strip().lower()
            return re.sub(r'\s+', ' ', str(row.get('activity_description', '')).strip().lower())
        df_reg['match_name'] = df_reg.apply(get_match, axis=1)
    else: df_reg['match_name'] = []

    comp_rows = []
    for _, trow in df_tgts.iterrows():
        d_id, b_id, t_act, t_target = trow['department_id'], trow.get('block_id'), trow.get('activity', ''), safe_int(trow.get('desired_target', 0))
        t_clean = re.sub(r'\s+', ' ', str(t_act).strip().lower())
        mask = (df_reg['department_id'] == d_id)
        if pd.notna(b_id) and b_id: mask &= (df_reg['block_id'] == b_id)
        candidate = df_reg[mask]
        entered = 0
        for _, rrow in candidate.iterrows():
            mn = rrow['match_name']
            if rrow.get('thematic_category_id') is not None: entered += (mn == t_clean)
            else: entered += (t_clean in mn)
        comp_rows.append({"Block": maps['block_map'].get(b_id, 'All'), "Department": maps['dept_map'].get(d_id, 'Unknown'), "Activity": t_act, "Target": t_target, "Entries": entered, "Gap": entered - t_target})
    
    if not comp_rows: st.info(f"No targets set for FY {active_fy}.")
    else:
        df_comp = pd.DataFrame(comp_rows)
        st.dataframe(df_comp.style.apply(lambda row: ['background:#e8f5e9;color:#1b5e20']*len(row) if row['Gap'] == 0 else ['background:#ffebee;color:#b71c1c']*len(row), axis=1), use_container_width=True, hide_index=True)

def render_audit_trail(user, role, supabase, maps):
    try:
        audit = supabase.table("progress_updates").select("*, convergence_register(id, activity_description, department_id, district_id, block_id), users(full_name, role)").order("updated_at", desc=True)
        if role != 'superadmin':
            if role == 'department': audit = audit.eq("convergence_register.department_id", user.get('department_id'))
            elif role == 'district': audit = audit.eq("convergence_register.district_id", user.get('district_id'))
            elif role == 'block': audit = audit.eq("convergence_register.block_id", user.get('block_id'))
        data = audit.execute().data or []
        if not data: st.info("No audit history found."); return
        
        rows = []
        for r in data:
            conv = r.get('convergence_register') or {}
            upd = r.get('users') or {}
            rows.append({
                "Date": pd.to_datetime(r.get('updated_at') or r.get('created_at')).strftime('%d %b %Y, %H:%M'),
                "Updater": upd.get('full_name', 'System'),
                "Work": conv.get('activity_description', 'Unknown'),
                "Status": r.get('status', 'N/A'),
                "Physical %": r.get('physical_achievement', 0),
                "Financial (₹L)": r.get('financial_achievement', 0.0),
                "Persondays": r.get('persondays_generated', 0),
                "Remarks": r.get('remarks', ''),
                "ID": r['id']
            })
        df = pd.DataFrame(rows)
        df = df[df.apply(lambda row: row.astype(str).str.contains(st.text_input("🔍 Search Audit"), case=False, na=False).any(), axis=1)] if st.text_input("🔍 Search Audit") else df
        st.dataframe(df[['Date', 'Updater', 'Work', 'Status', 'Physical %', 'Financial (₹L)', 'Persondays', 'Remarks']], use_container_width=True, hide_index=True)
    except Exception as e: st.error(f"Error loading audit: {e}")

def show():
    require_role('superadmin', 'district', 'block', 'department')
    user, role, supabase = get_current_user(), get_current_user()['role'], get_supabase()
    depts, wings, dists, blocks, acts, act_map, fys, users, themes = fetch_master_data()
    
    maps = {
        "dept_map": {d['id']: d['department_name'] for d in depts},
        "wing_map": {w['id']: w for w in wings},
        "block_map": {b['id']: b['block_name'] for b in blocks},
        "dist_map": {d['district_name']: d['id'] for d in dists},
        "dept_to_wings": {d: [w for w in wings if w['department_id'] == d] for d in set(w['department_id'] for w in wings)}
    }
    master_data = {"depts": depts, "wings": wings, "districts": dists, "blocks": blocks, "activities": acts, "act_dept_mapping": act_map, "fys": fys, "users": users, "themes": themes}
    
    active_fy = st.session_state.get("selected_fy", "2026-27")
    active_fy_id = next((f['id'] for f in fys if f.get('year_name') == active_fy), None)
    if not active_fy_id: st.warning("Please select an active FY in your profile.")

    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Department Targets", "🏗️ Implementation Progress", "🚨 Target Compliance", "📋 Audit Trail"])
    with tab1: render_department_targets(user, role, supabase, maps, master_data)
    with tab2: render_implementation_progress(user, role, supabase, maps, master_data)
    with tab3: render_target_compliance(user, role, supabase, maps, master_data, active_fy_id, active_fy)
    with tab4: render_audit_trail(user, role, supabase, maps)
    
    st.markdown("""<div style='text-align: center; margin-top:40px; color:#64748B; font-weight:600;'>Hooghly District Administration || District VB GRAM G Cell || Mail : nodal.hooghly@gmail.com</div>""", unsafe_allow_html=True)
