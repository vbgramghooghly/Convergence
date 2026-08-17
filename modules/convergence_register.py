import io
import pandas as pd
import streamlit as st
from auth.auth import get_current_user, require_role
from utils.audit import log_action
from utils.db import get_supabase

# ---------- CONSTANTS ----------
CONVERGENCE_TYPES = [
    "Technical Convergence (Zero Fund/NOC)",
    "Financial (as PIA)",
    "Financial (as Non-PIA)",
]
ORIGIN_SOURCES = ["District Plan", "Block Plan", "District Meeting", "Block Meeting"]
STATUS_OPTIONS = ["Planned", "Approved", "Under Implementation", "Completed", "Delayed", "Dropped"]

# ---------- HOOGHLY DISTRICT BLOCK → GP MAPPING (PRESERVED) ----------
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

# ---------- CACHED LOOKUP ----------
@st.cache_data(ttl=600)
def fetch_master_lookups():
    supabase = get_supabase()
    return {
        "fys": supabase.table("financial_years").select("*").eq("active", True).execute().data or [],
        "districts": supabase.table("districts").select("*").eq("active", True).execute().data or [],
        "blocks": supabase.table("blocks").select("*").eq("active", True).execute().data or [],
        "depts": supabase.table("departments").select("*").eq("active", True).execute().data or [],
        "themes": supabase.table("themes").select("*").eq("active", True).execute().data or [],
        "activities": supabase.table("activities").select("*").eq("active", True).execute().data or [],
        "act_dept_mapping": supabase.table("activity_departments").select("*").execute().data or [],
    }

# ---------- HELPERS ----------
def build_maps(data):
    return {
        "fy_map": {f["year_name"]: f["id"] for f in data["fys"]},
        "dist_map": {d["district_name"]: d["id"] for d in data["districts"]},
        "block_map": {b["block_name"]: b["id"] for b in data["blocks"]},
        "dept_map": {d["department_name"]: d["id"] for d in data["depts"]},
        "fy_reverse": {f["id"]: f["year_name"] for f in data["fys"]},
        "dist_reverse": {d["id"]: d["district_name"] for d in data["districts"]},
        "block_reverse": {b["id"]: b["block_name"] for b in data["blocks"]},
        "dept_reverse": {d["id"]: d["department_name"] for d in data["depts"]},
    }

def get_filtered_records(supabase, role, user):
    query = supabase.table("convergence_register").select("*")
    if role == "district":
        query = query.eq("district_id", user["district_id"])
    elif role == "block":
        query = query.eq("block_id", user["block_id"])
    elif role == "department":
        if not user.get("department_id"):
            st.error("🚨 Your account is missing a Department Assignment. Please contact Superadmin.")
            st.stop()
        query = query.eq("department_id", user["department_id"]).eq("district_id", user["district_id"])
    return query.execute().data or []

def render_kpi_cards(df):
    if df.empty:
        return
    total_fund = pd.to_numeric(df.get("total_converged_fund", 0), errors="coerce").sum()
    total_pdays = pd.to_numeric(df.get("expected_persondays", 0), errors="coerce").sum()
    active_count = len(df[df.get("current_status", "").isin(["Planned", "Approved", "Under Implementation"])])
    completed_count = len(df[df.get("current_status", "") == "Completed"])
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Works Registered", len(df))
    c2.metric("In Pipeline / Active", active_count)
    c3.metric("Completed Works", completed_count)
    c4.metric("Converged Fund", f"₹{total_fund:,.2f} L")
    c5.metric("Target Persondays", f"{int(total_pdays):,}")
    st.markdown("<br>", unsafe_allow_html=True)

def display_register(df, maps):
    if df.empty:
        st.info("No convergence activities found for your jurisdiction.")
        return
    df_display = df.copy()
    df_display["FY"] = df_display["financial_year_id"].map(maps["fy_reverse"]).fillna("N/A")
    df_display["District"] = df_display["district_id"].map(maps["dist_reverse"])
    df_display["Block"] = df_display["block_id"].map(maps["block_reverse"])
    df_display["Department"] = df_display["department_id"].map(maps["dept_reverse"])
    for col in ["convergence_type", "mis_code", "origin_source"]:
        if col not in df_display.columns:
            df_display[col] = "Not Specified" if col == "convergence_type" else ""
    
    # Add new columns if they exist
    if "department_scheme_convergence" in df_display.columns:
        df_display["Own Scheme Convergence"] = df_display["department_scheme_convergence"].map({True: "Yes", False: "No"})
    if "department_scheme_name" in df_display.columns:
        df_display["Scheme / Fund Name"] = df_display["department_scheme_name"]
    if "department_annual_plan_status" in df_display.columns:
        df_display["Own Annual Plan Status"] = df_display["department_annual_plan_status"]
    if "department_scheme_remarks" in df_display.columns:
        df_display["Remarks"] = df_display["department_scheme_remarks"]

    df_display.rename(
        columns={
            "activity_description": "Work Name",
            "geo_location": "Location Details",
            "origin_source": "Source",
            "convergence_type": "Convergence Type",
            "current_status": "Status",
            "total_converged_fund": "Total Fund (₹ Lakhs)"
        },
        inplace=True
    )
    display_cols = [
        "FY", "District", "Block", "Department", "Work Name",
        "Location Details", "Source", "Convergence Type", "Status", "Total Fund (₹ Lakhs)"
    ]
    # Append new columns if present
    extra_cols = [c for c in ["Own Scheme Convergence", "Scheme / Fund Name", "Own Annual Plan Status", "Remarks"] if c in df_display.columns]
    display_cols.extend(extra_cols)

    st.dataframe(df_display[display_cols], use_container_width=True, hide_index=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_display[display_cols].to_excel(writer, index=False, sheet_name="Convergence_Register")
    st.download_button(
        "📥 Export Register to Excel",
        data=buffer.getvalue(),
        file_name="convergence_register.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def render_scheme_convergence_section(defaults):
    """
    Renders the Departmental Scheme / Fund Convergence section.
    Returns a dict with the entered values.
    """
    st.markdown("##### Departmental Scheme / Fund Convergence")
    conv_choice = st.radio(
        "Convergence with Own Departmental Scheme / Fund?",
        options=["No", "Yes"],
        index=0 if not defaults.get("convergence") else 1,
        key="conv_choice_reg"
    )
    scheme_name = ""
    if conv_choice == "Yes":
        scheme_name = st.text_input(
            "Name of Departmental Scheme / Fund *",
            value=defaults.get("scheme_name", ""),
            key="scheme_name_reg"
        )
    annual_plan_status = st.selectbox(
        "Included in Department's Own Annual Plan?",
        options=["Yes", "No", "Not Confirmed"],
        index=["Yes", "No", "Not Confirmed"].index(defaults.get("annual_plan_status", "Not Confirmed")),
        key="annual_plan_status_reg"
    )
    scheme_remarks = st.text_area(
        "Departmental Scheme / Annual Plan Remarks (Optional)",
        value=defaults.get("scheme_remarks", ""),
        key="scheme_remarks_reg"
    )
    return {
        "convergence": conv_choice == "Yes",
        "scheme_name": scheme_name.strip() if scheme_name else None,
        "annual_plan_status": annual_plan_status,
        "scheme_remarks": scheme_remarks.strip() if scheme_remarks else None,
    }

def edit_delete_section(records, maps, supabase, user):
    if user["role"] not in ["superadmin", "district"] or not records:
        return
    st.markdown("---")
    st.markdown("#### 🛠️ Manage / Amend Existing Activity")
    with st.expander("✏️ Edit or 🗑️ Delete an Activity", expanded=False):
        display_options = {
            r["id"]: f"{r['activity_description'][:60]}... - {maps['dept_reverse'].get(r['department_id'], 'Unknown')} (₹{r.get('total_converged_fund', 0)} L)"
            for r in records
        }
        selected_edit_id = st.selectbox(
            "Select Activity to Modify",
            options=list(display_options.keys()),
            format_func=lambda x: display_options[x]
        )
        if not selected_edit_id:
            return
        rec = next(r for r in records if r["id"] == selected_edit_id)

        if st.button("🗑️ Permanently Delete Activity", type="primary"):
            try:
                supabase.table("convergence_register").delete().eq("id", selected_edit_id).execute()
                log_action(user.get("id"), f"DELETE convergence_register {selected_edit_id}")
                st.success("Activity deleted successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error deleting record: {e}")

        with st.form("edit_conv_form"):
            col_e1, col_e2 = st.columns(2)
            current_status = rec.get("current_status", "Planned")
            new_status = col_e1.selectbox("Status", STATUS_OPTIONS, index=STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0)
            current_conv = rec.get("convergence_type", CONVERGENCE_TYPES[0])
            new_conv_type = col_e2.selectbox("Convergence Type", CONVERGENCE_TYPES, index=CONVERGENCE_TYPES.index(current_conv) if current_conv in CONVERGENCE_TYPES else 0)

            new_work_name = st.text_input("Work Name*", value=rec.get("activity_description", "") or "")
            new_geo = st.text_input("Location Details & GP Mapping", value=rec.get("geo_location", "") or "")
            new_outcome = st.text_area("Possible Outcome / Work Dimensions", value=rec.get("work_dimensions", "") or "")

            col_det5, col_det6 = st.columns(2)
            new_mis = col_det5.text_input("MIS Code", value=rec.get("mis_code", "") or "")
            curr_origin = rec.get("origin_source", "District Plan")
            new_origin = col_det6.selectbox("Source of Activity", ORIGIN_SOURCES, index=ORIGIN_SOURCES.index(curr_origin) if curr_origin in ORIGIN_SOURCES else 0)

            col_t1, col_t2 = st.columns(2)
            new_d_fund = col_t1.number_input("Department Fund (₹ Lakhs)", value=float(rec.get("department_fund", 0.0)))
            new_v_fund = col_t2.number_input("VB-G RAM G Fund (₹ Lakhs)", value=float(rec.get("vbgramg_fund", 0.0)))
            new_pd = st.number_input("Expected Persondays*", value=int(rec.get("expected_persondays", 0)))

            # --- NEW: Departmental Scheme / Fund Convergence section in edit form ---
            defaults = {
                "convergence": rec.get("department_scheme_convergence", False),
                "scheme_name": rec.get("department_scheme_name", "") or "",
                "annual_plan_status": rec.get("department_annual_plan_status", "Not Confirmed"),
                "scheme_remarks": rec.get("department_scheme_remarks", "") or "",
            }
            scheme_data = render_scheme_convergence_section(defaults)

            if st.form_submit_button("Commit Changes", type="primary"):
                if new_conv_type == "Technical Convergence (Zero Fund/NOC)":
                    new_d_fund = new_v_fund = 0.0
                # Validation for new fields
                if scheme_data["convergence"] and not scheme_data["scheme_name"]:
                    st.error("⚠️ Scheme / Fund name is mandatory when Convergence = Yes.")
                elif not new_work_name.strip():
                    st.error("⚠️ Work Name cannot be empty.")
                elif new_conv_type != "Technical Convergence (Zero Fund/NOC)" and new_d_fund == 0.0 and new_v_fund == 0.0:
                    st.error("⚠️ Financial Convergence requires a Fund amount > 0.")
                elif new_pd <= 0:
                    st.error("⚠️ Expected Persondays is mandatory and must be greater than zero.")
                else:
                    update_payload = {
                        "current_status": new_status,
                        "convergence_type": new_conv_type,
                        "activity_description": new_work_name,
                        "scheme_name": None,
                        "geo_location": new_geo,
                        "work_dimensions": new_outcome,
                        "mis_code": new_mis.strip() if new_mis else None,
                        "origin_source": new_origin,
                        "expected_persondays": new_pd,
                        "department_fund": new_d_fund,
                        "vbgramg_fund": new_v_fund,
                        "department_scheme_convergence": scheme_data["convergence"],
                        "department_scheme_name": scheme_data["scheme_name"],
                        "department_annual_plan_status": scheme_data["annual_plan_status"],
                        "department_scheme_remarks": scheme_data["scheme_remarks"],
                    }
                    try:
                        supabase.table("convergence_register").update(update_payload).eq("id", selected_edit_id).execute()
                        log_action(user.get("id"), f"UPDATE convergence_register {selected_edit_id}")
                        st.success("Activity updated successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error updating record: {e}")

# ---------- MAIN UI ----------
def show():
    require_role("superadmin", "district", "block", "department")
    user = get_current_user()
    role = user["role"]
    supabase = get_supabase()

    master = fetch_master_lookups()
    maps = build_maps(master)
    records = get_filtered_records(supabase, role, user)
    df_records = pd.DataFrame(records) if records else pd.DataFrame()

    render_kpi_cards(df_records)

    tab1, tab2, tab3 = st.tabs([
        "📋 Master Work Register",
        "➕ Add New Activity",
        "📂 Bulk Upload (CSV)"
    ])

    with tab1:
        display_register(df_records, maps)
        edit_delete_section(records, maps, supabase, user)

    with tab2:
        st.markdown("#### ➕ Register Individual Convergence Activity")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            sel_fy = col1.selectbox("Financial Year*", list(maps["fy_map"].keys()))

            if role == "department":
                dept_default = next((d["department_name"] for d in master["depts"] if d["id"] == user.get("department_id")), None)
                if not dept_default:
                    st.error("🚨 Account not mapped to a department. Contact Superadmin.")
                    st.stop()
                sel_dept = col2.selectbox("Department*", [dept_default], disabled=True)
            else:
                sel_dept = col2.selectbox("Department*", list(maps["dept_map"].keys()))

            selected_dept_id = maps["dept_map"].get(sel_dept)

            if role in ["block", "district", "department"]:
                dist_default = next(d["district_name"] for d in master["districts"] if d["id"] == user["district_id"])
                sel_dist = col1.selectbox("District*", [dist_default], disabled=True)
            else:
                sel_dist = col1.selectbox("District*", list(maps["dist_map"].keys()))

            selected_dist_id = maps["dist_map"].get(sel_dist)
            filtered_blocks = [b["block_name"] for b in master["blocks"] if b["district_id"] == selected_dist_id]

            if role == "block":
                block_default = next(b["block_name"] for b in master["blocks"] if b["id"] == user["block_id"])
                sel_block = col2.selectbox("Block*", [block_default], disabled=True)
            else:
                sel_block = col2.selectbox("Block*", ["Select Block"] + filtered_blocks)

            # GP & Spatial Details
            st.markdown("##### 📍 Gram Panchayat (GP) & Spatial Details")
            block_key = str(sel_block).upper().replace("-", " ").strip()
            gps_in_block = HOOGHLY_GPS.get(block_key, [])
            gp_options = ["Select GP"] + gps_in_block if sel_block != "Select Block" else ["Select GP"]

            col_gp1, col_gp2, col_gp3 = st.columns(3)
            primary_gp = col_gp1.selectbox("Primary Gram Panchayat (GP)*", gp_options)
            has_add_gp = col_gp2.selectbox("Additional GP Covered?", ["No", "Yes"])
            additional_gp, add_gp_portion = "", ""
            if has_add_gp == "Yes":
                additional_gp = col_gp2.selectbox("Additional GP Name", gp_options)
                add_gp_portion = col_gp3.text_input("Portion in Addl. GP", placeholder="e.g. 2 km or 40%")

            # Thematic Category & Linkage
            st.markdown("##### 🏗️ Thematic Work Category & Linkage")
            mapped_act_ids = [m["activity_id"] for m in master["act_dept_mapping"] if m["department_id"] == selected_dept_id]
            valid_activities = [a for a in master["activities"] if a["id"] in mapped_act_ids]
            valid_act_names = [a["activity_name"] for a in valid_activities]

            col_act1, col_loc1 = st.columns(2)
            if not valid_act_names:
                st.warning(f"No approved activities found for {sel_dept}.")
                sel_act_name = col_act1.selectbox("Base Activity*", ["No activities available"], disabled=True)
                theme_id = None
            else:
                sel_act_name = col_act1.selectbox("Base Activity*", valid_act_names)
                selected_act_record = next((a for a in valid_activities if a["activity_name"] == sel_act_name), None)
                theme_id = selected_act_record["theme_id"] if selected_act_record else None

            inp_loc_details = col_loc1.text_input("Location Details*", placeholder="Village / Beneficiary Name / Chainage")
            auto_desc = f"{sel_act_name} at {inp_loc_details}" if sel_act_name and sel_act_name != "No activities available" and inp_loc_details else ""

            col_wn, col_ll = st.columns(2)
            final_work_name = col_wn.text_input("Work Name*", value=auto_desc)
            inp_lat_long = col_ll.text_input("Latitude & Longitude (Optional)", placeholder="e.g. 22.89, 88.01")

            sel_conv_type = st.selectbox("Type of Convergence*", CONVERGENCE_TYPES)

            # Targets & Financial Allocation
            st.markdown("##### 🎯 Targets & Financial Allocation")
            col_f1, col_f2 = st.columns(2)
            inp_origin = col_f1.selectbox("Source of Activity Linkage", ORIGIN_SOURCES)
            persondays = col_f2.number_input("Expected Persondays*", min_value=0)
            possible_outcome = st.text_area("Expected Deliverables / Outcome", placeholder="e.g. 50 farmers benefited, 1 AWC constructed")

            if sel_conv_type == "Technical Convergence (Zero Fund/NOC)":
                st.info("ℹ️ Technical Convergence selected: Fund involvement is automatically 0.0.")
                dept_fund = vbg_fund = 0.0
            else:
                col_f3, col_f4 = st.columns(2)
                dept_fund = col_f3.number_input("Department Fund (₹ Lakhs)", min_value=0.0, step=0.1)
                vbg_fund = col_f4.number_input("VB-G RAM G Fund (₹ Lakhs)", min_value=0.0, step=0.1)

            # --- NEW: Departmental Scheme / Fund Convergence section (creation) ---
            st.markdown("---")
            scheme_defaults = {"convergence": False, "scheme_name": "", "annual_plan_status": "Not Confirmed", "scheme_remarks": ""}
            scheme_data = render_scheme_convergence_section(scheme_defaults)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Commit Activity Registration", type="primary", use_container_width=True):
                errors = []
                if not valid_act_names:
                    errors.append("Approved activity required.")
                if sel_block == "Select Block":
                    errors.append("Please select a valid Block.")
                if primary_gp == "Select GP":
                    errors.append("Primary GP is mandatory.")
                if has_add_gp == "Yes" and additional_gp == "Select GP":
                    errors.append("Please choose a valid Additional GP Name.")
                if not inp_loc_details.strip():
                    errors.append("Location Details are mandatory.")
                if not final_work_name.strip():
                    errors.append("Work Name is mandatory.")
                if sel_conv_type != "Technical Convergence (Zero Fund/NOC)" and dept_fund == 0.0 and vbg_fund == 0.0:
                    errors.append("Financial Convergence requires a Fund allocation.")
                if persondays <= 0:
                    errors.append("Expected Persondays must be greater than zero.")
                # New validation
                if scheme_data["convergence"] and not scheme_data["scheme_name"]:
                    errors.append("Scheme / Fund name is mandatory when Convergence = Yes.")

                if errors:
                    for err in errors:
                        st.error(f"⚠️ {err}")
                else:
                    block_id = maps["block_map"].get(sel_block)
                    geo_string = f"Loc: {inp_loc_details} | GP: {primary_gp}"
                    if has_add_gp == "Yes" and additional_gp and additional_gp != "Select GP":
                        geo_string += f" | Addl GP: {additional_gp} (Portion: {add_gp_portion})"
                    if inp_lat_long:
                        geo_string += f" | GPS: {inp_lat_long}"

                    insert_data = {
                        "financial_year_id": maps["fy_map"][sel_fy],
                        "district_id": selected_dist_id,
                        "block_id": block_id,
                        "department_id": selected_dept_id,
                        "activity_description": final_work_name,
                        "thematic_category_id": theme_id,
                        "convergence_type": sel_conv_type,
                        "scheme_name": None,
                        "geo_location": geo_string,
                        "work_dimensions": possible_outcome,
                        "dimension_unit": "Outcome",
                        "origin_source": inp_origin,
                        "desired_target": 1,
                        "expected_persondays": persondays,
                        "department_fund": dept_fund,
                        "vbgramg_fund": vbg_fund,
                        "current_status": "Planned",
                        "department_scheme_convergence": scheme_data["convergence"],
                        "department_scheme_name": scheme_data["scheme_name"],
                        "department_annual_plan_status": scheme_data["annual_plan_status"],
                        "department_scheme_remarks": scheme_data["scheme_remarks"],
                    }
                    try:
                        res = supabase.table("convergence_register").insert(insert_data).execute()
                        log_action(user.get("id"), f"CREATE convergence_register {res.data[0]['id']}")
                        st.success("✅ Convergence activity successfully created and registered!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving record: {e}")

    with tab3:
        # Bulk upload remains unchanged; new columns are not included in the template to avoid breaking existing CSV imports.
        # If you wish to add them, extend the template and validation accordingly.
        st.markdown("#### 📂 Bulk Upload & Batch Ingestion")
        st.caption("Download the official CSV template, populate records, and import in bulk. **All activities are validated against approved department linkages.**")

        template_cols = [
            "Financial Year", "District", "Block", "Primary GP", "Additional GP", "Additional GP Portion",
            "Department", "Base Activity", "Work Name", "Location Details", "Latitude Longitude",
            "Convergence Type", "Source of Activity Linkage", "Possible Outcome", "Expected Persondays",
            "Department Fund", "VB-G RAM G Fund"
        ]
        template_df = pd.DataFrame(columns=template_cols)
        csv_template = template_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Step 1: Download CSV Ingestion Template",
            data=csv_template,
            file_name="convergence_bulk_upload_template.csv",
            mime="text/csv"
        )

        uploaded_file = st.file_uploader("Step 2: Upload Completed CSV", type="csv")
        if uploaded_file:
            df_upload = pd.read_csv(uploaded_file)
            st.write("Previewing Raw Ingestion Data:")
            st.dataframe(df_upload.head(4), use_container_width=True)

            if st.button("Validate & Execute Import", type="primary"):
                success_count = 0
                error_log = []

                with st.spinner("Validating master records and executing batch insertion..."):
                    for index, row in df_upload.iterrows():
                        try:
                            fy_str = str(row.get("Financial Year", "")).strip()
                            dist_str = str(row.get("District", "")).strip()
                            block_str = str(row.get("Block", "")).strip()
                            dept_str = str(row.get("Department", "")).strip()
                            act_str = str(row.get("Base Activity", "")).strip()
                            conv_str = str(row.get("Convergence Type", "")).strip()

                            fy_id = maps["fy_map"].get(fy_str)
                            dist_id = maps["dist_map"].get(dist_str)
                            block_id = maps["block_map"].get(block_str)
                            dept_id = maps["dept_map"].get(dept_str)

                            if not all([fy_id, dist_id, block_id, dept_id]):
                                error_log.append(f"Row {index+2}: Invalid Master Data references (FY/District/Block/Dept mismatch).")
                                continue

                            if conv_str not in CONVERGENCE_TYPES:
                                error_log.append(f"Row {index+2}: Invalid Convergence Type.")
                                continue

                            mapped_acts = [m["activity_id"] for m in master["act_dept_mapping"] if m["department_id"] == dept_id]
                            valid_acts_for_dept = [a for a in master["activities"] if a["id"] in mapped_acts]
                            target_act = next((a for a in valid_acts_for_dept if a["activity_name"].lower() == act_str.lower()), None)

                            if not target_act:
                                error_log.append(f"Row {index+2}: Base Activity '{act_str}' is NOT approved for {dept_str}.")
                                continue

                            if conv_str == "Technical Convergence (Zero Fund/NOC)":
                                d_fund = m_fund = 0.0
                            else:
                                d_fund = float(row.get("Department Fund", 0) if pd.notna(row.get("Department Fund")) else 0)
                                m_fund = float(row.get("VB-G RAM G Fund", 0) if pd.notna(row.get("VB-G RAM G Fund")) else 0)
                                if d_fund == 0.0 and m_fund == 0.0:
                                    error_log.append(f"Row {index+2}: Financial Convergence requires a Fund amount > 0.")
                                    continue

                            expected_pd = int(row.get("Expected Persondays", 0) if pd.notna(row.get("Expected Persondays")) else 0)
                            if expected_pd <= 0:
                                error_log.append(f"Row {index+2}: Expected Persondays must be > 0.")
                                continue

                            origin_val = str(row.get("Source of Activity Linkage", "District Plan")).strip() if pd.notna(row.get("Source of Activity Linkage")) else "District Plan"
                            if origin_val not in ORIGIN_SOURCES:
                                origin_val = "District Plan"

                            loc_val = str(row.get("Location Details", "")).strip() if pd.notna(row.get("Location Details")) else "Unspecified Location"
                            gp_val = str(row.get("Primary GP", "")).strip() if pd.notna(row.get("Primary GP")) else ""
                            add_gp_val = str(row.get("Additional GP", "")).strip() if pd.notna(row.get("Additional GP")) else ""
                            add_gp_por = str(row.get("Additional GP Portion", "")).strip() if pd.notna(row.get("Additional GP Portion")) else ""
                            gps_val = str(row.get("Latitude Longitude", "")).strip() if pd.notna(row.get("Latitude Longitude")) else ""

                            work_name_val = str(row.get("Work Name", "")).strip() if pd.notna(row.get("Work Name")) else ""
                            if not work_name_val:
                                work_name_val = f"{target_act['activity_name']} at {loc_val}"

                            bulk_geo_string = f"Loc: {loc_val}"
                            if gp_val:
                                bulk_geo_string += f" | GP: {gp_val}"
                            if add_gp_val:
                                bulk_geo_string += f" | Addl GP: {add_gp_val} (Portion: {add_gp_por})"
                            if gps_val:
                                bulk_geo_string += f" | GPS: {gps_val}"

                            insert_data = {
                                "financial_year_id": fy_id,
                                "district_id": dist_id,
                                "block_id": block_id,
                                "department_id": dept_id,
                                "activity_description": work_name_val,
                                "thematic_category_id": target_act["theme_id"],
                                "convergence_type": conv_str,
                                "scheme_name": None,
                                "geo_location": bulk_geo_string,
                                "work_dimensions": str(row.get("Possible Outcome", "")).strip() if pd.notna(row.get("Possible Outcome")) else None,
                                "dimension_unit": "Outcome",
                                "origin_source": origin_val,
                                "desired_target": 1,
                                "expected_persondays": expected_pd,
                                "department_fund": d_fund,
                                "vbgramg_fund": m_fund,
                                "current_status": "Planned",
                                # New fields left NULL for bulk upload (optional)
                                "department_scheme_convergence": False,
                                "department_scheme_name": None,
                                "department_annual_plan_status": "Not Confirmed",
                                "department_scheme_remarks": None,
                            }
                            supabase.table("convergence_register").insert(insert_data).execute()
                            success_count += 1
                        except Exception as e:
                            error_log.append(f"Row {index+2}: Failed with error: {str(e)}")

                if success_count > 0:
                    st.success(f"✅ Successfully ingested {success_count} activities into the Master Register!")
                if error_log:
                    st.error(f"⚠️ {len(error_log)} rows failed validation:")
                    with st.expander("Inspect Validation Error Log"):
                        for err in error_log:
                            st.write(err)
                if success_count > 0 and not error_log:
                    st.rerun()
