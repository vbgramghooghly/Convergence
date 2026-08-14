import io
import pandas as pd
import streamlit as st
from auth.auth import get_current_user, require_role
from utils.audit import log_action
from utils.db import get_supabase
from utils.theme import apply_global_theme

def show():
    # 1. Apply the global theme immediately
    theme = apply_global_theme()
    
    # 2. Render Page Content
    # Use the app_name from the global theme if needed
    st.markdown(f"<h1>{theme.get('app_name')} Dashboard</h1>", unsafe_allow_html=True)
# --- HOOGHLY DISTRICT BLOCK TO GP MAPPING ---
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

def inject_custom_css():
    """Injects custom CSS to hide the Streamlit toolbar (Fork/GitHub buttons)."""
    st.markdown(
        """
        <style>
        /* Hide Streamlit toolbar (Fork and GitHub buttons) */
        .stAppToolbar {
            visibility: hidden !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show():
    require_role("superadmin", "district", "block", "department")

    # Apply custom UI styling to hide top-right toolbar elements
    inject_custom_css()

    st.title("Convergence Register")
    supabase = get_supabase()
    user = get_current_user()
    role = user["role"]

    # ==========================================
    # 1. FETCH MASTER DATA FOR LOOKUPS & MAPPING
    # ==========================================
    fys = supabase.table("financial_years").select("*").eq("active", True).execute().data
    districts = supabase.table("districts").select("*").eq("active", True).execute().data
    blocks = supabase.table("blocks").select("*").eq("active", True).execute().data
    depts = supabase.table("departments").select("*").eq("active", True).execute().data
    themes = supabase.table("themes").select("*").eq("active", True).execute().data

    activities = supabase.table("activities").select("*").eq("active", True).execute().data
    act_dept_mapping = supabase.table("activity_departments").select("*").execute().data

    # Forward maps (Name -> ID) for Forms
    fy_map = {f["year_name"]: f["id"] for f in fys}
    dist_map = {d["district_name"]: d["id"] for d in districts}
    block_map = {b["block_name"]: b["id"] for b in blocks}
    dept_map = {d["department_name"]: d["id"] for d in depts}
    theme_map_id_to_name = {t["id"]: t["theme_name"] for t in themes}

    # Reverse maps (ID -> Name) for Displaying the Dataframe safely
    fy_reverse_map = {f["id"]: f["year_name"] for f in fys}
    dist_reverse_map = {d["id"]: d["district_name"] for d in districts}
    block_reverse_map = {b["id"]: b["block_name"] for b in blocks}
    dept_reverse_map = {d["id"]: d["department_name"] for d in depts}

    CONVERGENCE_TYPES = [
        "Technical Convergence (Zero Fund/NOC)",
        "Financial (as PIA)",
        "Financial (as Non-PIA)",
    ]

    ORIGIN_SOURCES = [
        "District Plan",
        "Block Plan",
        "District Meeting",
        "Block Meeting",
    ]

    # ==========================================
    # 2. VIEW EXISTING RECORDS
    # ==========================================
    query = supabase.table("convergence_register").select("*")

    if role == "district":
        query = query.eq("district_id", user["district_id"])
    elif role == "block":
        query = query.eq("block_id", user["block_id"])
    elif role == "department":
        if not user.get("department_id"):
            st.error(
                "🚨 Your user account is missing a Department Assignment. Please"
                " contact Superadmin."
            )
            st.stop()
        query = query.eq("department_id", user["department_id"]).eq(
            "district_id", user["district_id"]
        )

    try:
        records = query.execute().data
    except Exception as e:
        st.error(f"Database error while fetching records: {e}")
        records = []

    st.subheader(f"Convergence Activities ({len(records)} records)")

    if records:
        df_display = pd.DataFrame(records)

        fy_col = (
            "financial_year_id"
            if "financial_year_id" in df_display.columns
            else "financial_year"
        )
        if fy_col in df_display.columns:
            df_display["FY"] = (
                df_display[fy_col]
                .map(fy_reverse_map)
                .fillna(df_display[fy_col])
            )
        else:
            df_display["FY"] = "N/A"

        df_display["District"] = df_display["district_id"].map(dist_reverse_map)
        df_display["Block"] = df_display["block_id"].map(block_reverse_map)
        df_display["Department"] = df_display["department_id"].map(dept_reverse_map)

        if "convergence_type" not in df_display.columns:
            df_display["convergence_type"] = "Not Specified"
        if "mis_code" not in df_display.columns:
            df_display["mis_code"] = ""
        if "origin_source" not in df_display.columns:
            df_display["origin_source"] = "District Plan"

        # Rename columns cleanly for professional tabular display
        df_display.rename(columns={
            "activity_description": "Work Name",
            "geo_location": "Location Details",
            "origin_source": "Source",
            "convergence_type": "Convergence Type",
            "current_status": "Status",
            "total_converged_fund": "Total Fund (₹ Lakhs)"
        }, inplace=True)

        display_cols = [
            "FY",
            "District",
            "Block",
            "Department",
            "Work Name",
            "Location Details",
            "Source",
            "Convergence Type",
            "Status",
            "Total Fund (₹ Lakhs)",
        ]

        st.dataframe(
            df_display[display_cols], use_container_width=True, hide_index=True
        )
    else:
        st.info("No records found.")

    # ==========================================
    # 2.5 MANAGE (EDIT/DELETE) SAVED ENTRIES
    # ==========================================
    if role in ["superadmin", "district"] and records:
        st.markdown("---")
        st.subheader("🛠️ Manage (Edit / Delete) Saved Entries")

        with st.expander("✏️ Edit or 🗑️ Delete an Activity", expanded=False):
            display_options = {
                r["id"]: (
                    f"{r['activity_description'][:60]}... -"
                    f" {dept_reverse_map.get(r['department_id'], 'Unknown')}"
                    f" (₹{r.get('total_converged_fund', 0)} Lakhs)"
                )
                for r in records
            }

            selected_edit_id = st.selectbox(
                "Select Activity to Manage",
                options=list(display_options.keys()),
                format_func=lambda x: display_options[x],
            )

            if selected_edit_id:
                rec = next(r for r in records if r["id"] == selected_edit_id)

                if st.button("🗑️ Permanently Delete Activity", type="primary"):
                    try:
                        (
                            supabase.table("convergence_register")
                            .delete()
                            .eq("id", selected_edit_id)
                            .execute()
                        )
                        try:
                            log_action(
                                user.get("id"),
                                f"DELETE convergence_register {selected_edit_id}",
                            )
                        except Exception:
                            pass
                        st.success("Activity deleted successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting record: {e}")

                st.markdown("#### Edit Details")
                with st.form("edit_conv_form"):
                    col_e1, col_e2 = st.columns(2)

                    status_opts = [
                        "Planned",
                        "Approved",
                        "Under Implementation",
                        "Completed",
                        "Delayed",
                    ]
                    current_status = rec.get("current_status", "Planned")
                    new_status = col_e1.selectbox(
                        "Update Status",
                        status_opts,
                        index=(
                            status_opts.index(current_status)
                            if current_status in status_opts
                            else 0
                        ),
                    )

                    current_conv = rec.get("convergence_type", CONVERGENCE_TYPES[0])
                    new_conv_type = col_e2.selectbox(
                        "Convergence Type",
                        CONVERGENCE_TYPES,
                        index=(
                            CONVERGENCE_TYPES.index(current_conv)
                            if current_conv in CONVERGENCE_TYPES
                            else 0
                        ),
                    )

                    st.markdown("##### Detailed Work Specifications")
                    new_work_name = st.text_input("Work Name*", value=rec.get("activity_description", "") or "")
                    new_geo = st.text_input(
                        "Location Details & GP Mapping",
                        value=rec.get("geo_location", "") or "",
                    )
                    
                    new_outcome = st.text_area(
                        "Possible Outcome / Work Dimensions", 
                        value=rec.get("work_dimensions", "") or ""
                    )

                    col_det5, col_det6 = st.columns(2)
                    new_mis = col_det5.text_input(
                        "MIS Code", value=rec.get("mis_code", "") or ""
                    )
                    curr_origin = rec.get("origin_source", "District Plan")
                    new_origin = col_det6.selectbox(
                        "Source of Activity Linkage",
                        ORIGIN_SOURCES,
                        index=(
                            ORIGIN_SOURCES.index(curr_origin)
                            if curr_origin in ORIGIN_SOURCES
                            else 0
                        ),
                    )

                    st.markdown("##### Targets & Financials")
                    col_t1, col_t2 = st.columns(2)
                    
                    new_d_fund = col_t1.number_input(
                        "Department Fund (₹ Lakhs)",
                        value=float(rec.get("department_fund", 0.0)),
                    )
                    new_v_fund = col_t2.number_input(
                        "VB-G RAM G Fund (₹ Lakhs)",
                        value=float(rec.get("vbgramg_fund", 0.0)),
                    )
                    new_pd = st.number_input(
                        "Expected Persondays*", value=int(rec.get("expected_persondays", 0))
                    )

                    if st.form_submit_button("Update Activity Details"):
                        if new_conv_type == "Technical Convergence (Zero Fund/NOC)":
                            new_d_fund = 0.0
                            new_v_fund = 0.0

                        # Validations
                        if not new_work_name.strip():
                            st.error("⚠️ Work Name cannot be empty.")
                        elif new_conv_type != "Technical Convergence (Zero Fund/NOC)" and new_d_fund == 0.0 and new_v_fund == 0.0:
                            st.error("⚠️ Financial Convergence requires a Fund amount. Please enter Department Fund or VB-G RAM G Fund.")
                        elif new_pd <= 0:
                            st.error("⚠️ Expected Persondays is a mandatory field and must be greater than zero.")
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
                            }
                            try:
                                (
                                    supabase.table("convergence_register")
                                    .update(update_payload)
                                    .eq("id", selected_edit_id)
                                    .execute()
                                )
                                try:
                                    log_action(
                                        user.get("id"),
                                        f"UPDATE convergence_register {selected_edit_id}",
                                    )
                                except Exception:
                                    pass
                                st.success("Activity updated successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating record: {e}")

    st.markdown("---")

    # ==========================================
    # 3. MANUAL ENTRY FORM (Dynamic Layout)
    # ==========================================
    with st.expander("➕ Add New Convergence Activity", expanded=True):
        col1, col2 = st.columns(2)

        sel_fy = col1.selectbox("Financial Year*", list(fy_map.keys()))

        if role == "department":
            dept_default = next(
                (
                    d["department_name"]
                    for d in depts
                    if d["id"] == user.get("department_id")
                ),
                None,
            )
            if not dept_default:
                st.error(
                    "🚨 Your account is not mapped to any specific department. Please"
                    " contact the Superadmin."
                )
                st.stop()
            sel_dept = col2.selectbox("Department*", [dept_default], disabled=True)
        else:
            sel_dept = col2.selectbox("Department*", list(dept_map.keys()))

        selected_dept_id = dept_map.get(sel_dept)

        if role in ["block", "district", "department"]:
            dist_default = next(
                d["district_name"] for d in districts if d["id"] == user["district_id"]
            )
            sel_dist = col1.selectbox("District*", [dist_default], disabled=True)
        else:
            sel_dist = col1.selectbox("District*", list(dist_map.keys()))

        selected_dist_id = dist_map.get(sel_dist)

        filtered_blocks = [
            b["block_name"]
            for b in blocks
            if b["district_id"] == selected_dist_id
        ]

        # Block Selection
        if role == "block":
            block_default = next(
                b["block_name"] for b in blocks if b["id"] == user["block_id"]
            )
            sel_block = col2.selectbox("Block*", [block_default], disabled=True)
        else:
            sel_block = col2.selectbox("Block*", ["Select Block"] + filtered_blocks)

        # Dynamic GP Loading Logic based on Block
        st.markdown("##### 📍 Gram Panchayat (GP) & Location Mapping")
        
        # Clean block name for mapping
        block_key = str(sel_block).upper().replace("-", " ").strip()
        gps_in_block = HOOGHLY_GPS.get(block_key, [])
        gp_options = ["Select GP"] + gps_in_block if sel_block != "Select Block" else ["Select GP"]
        
        col_gp1, col_gp2, col_gp3 = st.columns(3)
        primary_gp = col_gp1.selectbox("Primary Gram Panchayat (GP)*", gp_options)
        
        has_add_gp = col_gp2.selectbox("Additional GP Covered?", ["No", "Yes"])
        additional_gp = ""
        add_gp_portion = ""
        if has_add_gp == "Yes":
            additional_gp = col_gp2.selectbox("Additional GP Name", gp_options)
            add_gp_portion = col_gp3.text_input("Portion in Addl. GP", placeholder="e.g., 2 km or 40%")

        st.markdown("##### 🏗️ Activity & Convergence Type")

        mapped_act_ids = [
            m["activity_id"]
            for m in act_dept_mapping
            if m["department_id"] == selected_dept_id
        ]
        valid_activities = [a for a in activities if a["id"] in mapped_act_ids]
        valid_act_names = [a["activity_name"] for a in valid_activities]

        col_act1, col_loc1 = st.columns(2)

        if not valid_act_names:
            st.warning(f"No approved activities found for {sel_dept}.")
            sel_act_name = col_act1.selectbox(
                "Base Activity / Work Category*",
                ["No activities available"],
                disabled=True,
            )
            theme_id = None
        else:
            sel_act_name = col_act1.selectbox(
                "Base Activity / Work Category*", valid_act_names
            )
            selected_act_record = next(
                (a for a in valid_activities if a["activity_name"] == sel_act_name),
                None,
            )
            theme_id = (
                selected_act_record["theme_id"] if selected_act_record else None
            )

        inp_loc_details = col_loc1.text_input(
            "Location Details*", 
            placeholder="Village / Beneficiary Name / From X to Y / Chainage"
        )
        
        # --- AUTO GENERATED DESCRIPTION LOGIC INSIDE EDITABLE TEXT INPUT ---
        auto_desc = ""
        if sel_act_name and sel_act_name != "No activities available" and inp_loc_details:
            auto_desc = f"{sel_act_name} at {inp_loc_details}"

        col_wn, col_ll = st.columns(2)
        # The value automatically updates based on above, but remains an editable field!
        final_work_name = col_wn.text_input("Work Name*", value=auto_desc)
        
        inp_lat_long = col_ll.text_input(
            "Latitude & Longitude (Optional)", placeholder="e.g., 22.89, 88.01"
        )

        sel_conv_type = st.selectbox("Type of Convergence*", CONVERGENCE_TYPES)

        st.markdown("##### 🎯 Targets & Financials")
        col_f1, col_f2 = st.columns(2)
        inp_origin = col_f1.selectbox("Source of Activity Linkage", ORIGIN_SOURCES)
        
        st.caption("ℹ️ *Overall Physical Targets are linked directly with the Department's Yearly Target limits. Define the specific localized outcome for this entry below:*")
        possible_outcome = st.text_area("Possible Outcome / Deliverables", placeholder="e.g., 50 farmers benefited, 2km road built, 1 Anganwadi Center constructed")
        
        persondays = col_f2.number_input("Expected Persondays*", min_value=0)

        if sel_conv_type == "Technical Convergence (Zero Fund/NOC)":
            st.info(
                "ℹ️ Technical Convergence selected: Fund involvement is automatically"
                " set to zero."
            )
            dept_fund = 0.0
            vbg_fund = 0.0
        else:
            col_f3, col_f4 = st.columns(2)
            dept_fund = col_f3.number_input(
                "Department Fund (₹ Lakhs)", min_value=0.0, step=0.1
            )
            vbg_fund = col_f4.number_input(
                "VB-G RAM G Fund (₹ Lakhs)", min_value=0.0, step=0.1
            )

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.button(
            "Save Convergence Activity", type="primary", use_container_width=True
        )

        if submitted:
            # Validations 
            if not valid_act_names:
                st.error("Cannot save without a valid approved activity.")
            elif sel_block == "Select Block":
                st.error("Please select a valid Block to proceed.")
            elif primary_gp == "Select GP":
                st.error("Primary Gram Panchayat (GP) is a mandatory field.")
            elif has_add_gp == "Yes" and additional_gp == "Select GP":
                st.error("You selected 'Yes' for Additional GP. Please choose a valid Additional GP Name.")
            elif not inp_loc_details.strip():
                st.error("Location Details are mandatory to structure the geographical mapping.")
            elif not final_work_name.strip():
                st.error("Work Name is mandatory.")
            elif sel_conv_type != "Technical Convergence (Zero Fund/NOC)" and dept_fund == 0.0 and vbg_fund == 0.0:
                st.error("⚠️ Financial Convergence requires a Fund amount. Please enter Department Fund or VB-G RAM G Fund.")
            elif persondays <= 0:
                st.error("⚠️ Expected Persondays is a mandatory field and must be greater than zero.")
            else:
                block_id = block_map.get(sel_block)
                
                # Safely pack all location data into the geo_location string
                geo_string = f"Loc: {inp_loc_details} | GP: {primary_gp}"
                if has_add_gp == "Yes" and additional_gp and additional_gp != "Select GP":
                    geo_string += f" | Addl GP: {additional_gp} (Portion: {add_gp_portion})"
                if inp_lat_long:
                    geo_string += f" | GPS: {inp_lat_long}"

                insert_data = {
                    "financial_year_id": fy_map[sel_fy],
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
                    "desired_target": 1, # Set to 1 as each entry represents an individual scheme/asset
                    "expected_persondays": persondays,
                    "department_fund": dept_fund,
                    "vbgramg_fund": vbg_fund,
                    "current_status": "Planned",
                }

                try:
                    res = (
                        supabase.table("convergence_register")
                        .insert(insert_data)
                        .execute()
                    )
                    try:
                        log_action(
                            user.get("id"),
                            f"CREATE convergence_register {res.data[0]['id']}",
                        )
                    except Exception:
                        pass
                    st.success("✅ 1 activity successfully auto-generated, captured and recorded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving record: {e}")

    # ==========================================
    # 4. BULK UPLOAD MODULE
    # ==========================================
    st.markdown("---")
    st.subheader("📂 Bulk Upload Activities")
    st.caption(
        "1st download the template, populate it, then reupload. **Only approved activities for the specified department will be accepted.**"
    )

    # Generate CSV Template dynamically 
    template_df = pd.DataFrame(columns=[
        "Financial Year", "District", "Block", "Primary GP", "Additional GP", "Additional GP Portion",
        "Department", "Base Activity", "Work Name", "Location Details", "Latitude Longitude",
        "Convergence Type", "Source of Activity Linkage", "Possible Outcome", "Expected Persondays",
        "Department Fund", "VB-G RAM G Fund"
    ])
    csv_template = template_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 1st: Download CSV Template",
        data=csv_template,
        file_name="convergence_bulk_upload_template.csv",
        mime="text/csv",
    )

    uploaded_file = st.file_uploader("2nd: Upload Populated CSV", type="csv")

    if uploaded_file:
        df_upload = pd.read_csv(uploaded_file)
        st.write("Preview of Uploaded Data:")
        st.dataframe(df_upload.head(3), use_container_width=True)

        if st.button("Validate & Import Data", type="primary"):
            success_count = 0
            error_log = []

            with st.spinner("Processing records..."):
                for index, row in df_upload.iterrows():
                    try:
                        fy_str = str(row.get("Financial Year", "")).strip()
                        dist_str = str(row.get("District", "")).strip()
                        block_str = str(row.get("Block", "")).strip()
                        dept_str = str(row.get("Department", "")).strip()
                        act_str = str(row.get("Base Activity", "")).strip()
                        conv_str = str(row.get("Convergence Type", "")).strip()

                        fy_id = fy_map.get(fy_str)
                        dist_id = dist_map.get(dist_str)
                        block_id = block_map.get(block_str)
                        dept_id = dept_map.get(dept_str)

                        if not all([fy_id, dist_id, block_id, dept_id]):
                            error_log.append(
                                f"Row {index+2}: Invalid Master Data references (Ensure FY, District, Block, and Department are provided and exact matches)."
                            )
                            continue

                        if conv_str not in CONVERGENCE_TYPES:
                            error_log.append(f"Row {index+2}: Invalid Convergence Type. Must match template exactly.")
                            continue

                        mapped_acts = [m["activity_id"] for m in act_dept_mapping if m["department_id"] == dept_id]
                        valid_acts_for_dept = [a for a in activities if a["id"] in mapped_acts]
                        target_act = next(
                            (a for a in valid_acts_for_dept if a["activity_name"].lower() == act_str.lower()), None,
                        )

                        if not target_act:
                            error_log.append(f"Row {index+2}: Base Activity '{act_str}' is NOT approved for {dept_str}.")
                            continue
                            
                        # Validations for Funds & Persondays
                        if conv_str == "Technical Convergence (Zero Fund/NOC)":
                            d_fund = 0.0
                            m_fund = 0.0
                        else:
                            d_fund = float(row.get("Department Fund", 0) if pd.notna(row.get("Department Fund")) else 0)
                            m_fund = float(row.get("VB-G RAM G Fund", 0) if pd.notna(row.get("VB-G RAM G Fund")) else 0)
                            if d_fund == 0.0 and m_fund == 0.0:
                                error_log.append(f"Row {index+2}: Financial Convergence requires a Fund amount > 0.")
                                continue
                                
                        expected_pd = int(row.get("Expected Persondays", 0) if pd.notna(row.get("Expected Persondays")) else 0)
                        if expected_pd <= 0:
                            error_log.append(f"Row {index+2}: Expected Persondays must be greater than 0.")
                            continue

                        origin_val = str(row.get("Source of Activity Linkage", "District Plan")).strip() if pd.notna(row.get("Source of Activity Linkage")) else "District Plan"
                        if origin_val not in ORIGIN_SOURCES:
                            origin_val = "District Plan"

                        # Extract Location & String generation data
                        loc_val = str(row.get("Location Details", "")).strip() if pd.notna(row.get("Location Details")) else "Unspecified Location"
                        gp_val = str(row.get("Primary GP", "")).strip() if pd.notna(row.get("Primary GP")) else ""
                        add_gp_val = str(row.get("Additional GP", "")).strip() if pd.notna(row.get("Additional GP")) else ""
                        add_gp_por = str(row.get("Additional GP Portion", "")).strip() if pd.notna(row.get("Additional GP Portion")) else ""
                        gps_val = str(row.get("Latitude Longitude", "")).strip() if pd.notna(row.get("Latitude Longitude")) else ""
                        
                        # Generate Auto Description for bulk
                        work_name_val = str(row.get("Work Name", "")).strip() if pd.notna(row.get("Work Name")) else ""
                        if not work_name_val:
                            work_name_val = f"{target_act['activity_name']} at {loc_val}"
                        
                        # Pack Geography
                        bulk_geo_string = f"Loc: {loc_val}"
                        if gp_val: bulk_geo_string += f" | GP: {gp_val}"
                        if add_gp_val: bulk_geo_string += f" | Addl GP: {add_gp_val} (Portion: {add_gp_por})"
                        if gps_val: bulk_geo_string += f" | GPS: {gps_val}"

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
                            "desired_target": 1, # Set to 1 as each entry represents an individual scheme/asset
                            "expected_persondays": expected_pd,
                            "department_fund": d_fund,
                            "vbgramg_fund": m_fund,
                            "current_status": "Planned",
                        }

                        supabase.table("convergence_register").insert(insert_data).execute()
                        success_count += 1

                    except Exception as e:
                        error_log.append(f"Row {index+2}: Failed to process due to error: {str(e)}")

            if success_count > 0:
                st.success(f"✅ Successfully imported and generated {success_count} activities!")

            if error_log:
                st.error(f"{len(error_log)} rows failed validation and were skipped.")
                with st.expander("View Error Details"):
                    for err in error_log:
                        st.write(err)

            if success_count > 0 and not error_log:
                st.rerun()
