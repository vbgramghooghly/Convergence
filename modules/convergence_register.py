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
PIA_OPTIONS = ["Select PIA", "GP", "Block", "Department", "Other"]

# ---------- CACHED LOOKUP ----------
@st.cache_data(ttl=600)
def fetch_master_lookups():
    supabase = get_supabase()
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

def build_maps(data):
    return {
        "fy_name_to_id": {f["year_name"].strip(): f["id"] for f in data["fys"]},
        "dist_map": {d["district_name"].strip(): d["id"] for d in data["districts"]},
        "block_map": {b["block_name"].strip(): b["id"] for b in data["blocks"]},
        "dept_map": {d["department_name"].strip(): d["id"] for d in data["depts"]},
        "wing_map": {w["id"]: w for w in data["wings"]},
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

def get_record_count(supabase, role, user):
    query = supabase.table("convergence_register").select("*", count="exact", head=True)
    if role == "district":
        query = query.eq("district_id", user["district_id"])
    elif role == "block":
        query = query.eq("block_id", user["block_id"])
    elif role == "department":
        if not user.get("department_id"): return 0
        query = query.eq("department_id", user["department_id"]).eq("district_id", user["district_id"])
    return query.execute().count

def render_kpi_cards(df, exact_count):
    if df.empty:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Works Registered", exact_count)
        c2.metric("In Pipeline / Active", 0)
        c3.metric("Completed Works", 0)
        c4.metric("Converged Fund", "₹0.00 L")
        c5.metric("Target Persondays", "0")
        st.markdown("<br>", unsafe_allow_html=True)
        return

    total_fund = pd.to_numeric(df.get("total_converged_fund", 0), errors="coerce").sum()
    total_pdays = pd.to_numeric(df.get("expected_persondays", 0), errors="coerce").sum()
    active_count = len(df[df.get("current_status", "").isin(["Planned", "Approved", "Under Implementation"])])
    completed_count = len(df[df.get("current_status", "") == "Completed"])
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Works Registered", exact_count)
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
    
    df_display["Wing"] = df_display["wing_id"].apply(
        lambda x: maps["wing_map"].get(x, {}).get("wing_name", "Direct Parent Department") if pd.notna(x) and x else "Direct Parent Department"
    )

    def extract_base_activity(desc):
        if not desc:
            return ""
        if " at " in desc:
            return desc.split(" at ", 1)[0].strip()
        return desc.strip()
    df_display["Base Activity"] = df_display["activity_description"].apply(extract_base_activity)

    for col in ["convergence_type", "mis_code", "origin_source"]:
        if col not in df_display.columns: df_display[col] = "Not Specified" if col == "convergence_type" else ""
    
    if "department_scheme_convergence" in df_display.columns:
        df_display["Own Scheme Convergence"] = df_display["department_scheme_convergence"].map({True: "Yes", False: "No"})
    if "department_scheme_name" in df_display.columns: df_display["Scheme / Fund Name"] = df_display["department_scheme_name"]
    if "department_annual_plan_status" in df_display.columns: df_display["Own Annual Plan Status"] = df_display["department_annual_plan_status"]
    if "department_scheme_remarks" in df_display.columns: df_display["Remarks"] = df_display["department_scheme_remarks"]
    if "pia_type" in df_display.columns: df_display["PIA (Implementing Agency)"] = df_display["pia_type"]

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
        "FY", "District", "Block", "Department", "Wing",
        "Base Activity",
        "Work Name",
        "Location Details", "Source", "Convergence Type", "Status", "Total Fund (₹ Lakhs)"
    ]
    extra_cols = [c for c in ["PIA (Implementing Agency)", "Own Scheme Convergence", "Scheme / Fund Name", "Own Annual Plan Status", "Remarks"] if c in df_display.columns]
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

def render_scheme_convergence_section(defaults, key_prefix=""):
    st.markdown("##### Departmental Scheme / Fund Convergence")
    conv_choice = st.radio(
        "Convergence with Own Departmental Scheme / Fund?",
        options=["No", "Yes"],
        index=0 if not defaults.get("convergence") else 1,
        key=f"{key_prefix}_conv_choice"
    )
    scheme_name = ""
    if conv_choice == "Yes":
        scheme_name = st.text_input(
            "Name of Departmental Scheme / Fund *",
            value=defaults.get("scheme_name", ""),
            key=f"{key_prefix}_scheme_name"
        )
    status_options = ["Yes", "No", "Not Confirmed"]
    default_status = defaults.get("annual_plan_status", "Not Confirmed")
    if default_status not in status_options: default_status = "Not Confirmed"
    default_index = status_options.index(default_status)
    annual_plan_status = st.selectbox(
        "Included in Department's Own Annual Plan?",
        options=status_options,
        index=default_index,
        key=f"{key_prefix}_annual_status"
    )
    scheme_remarks = st.text_area(
        "Departmental Scheme / Annual Plan Remarks (Optional)",
        value=defaults.get("scheme_remarks", ""),
        key=f"{key_prefix}_scheme_remarks"
    )
    return {
        "convergence": conv_choice == "Yes",
        "scheme_name": scheme_name.strip() if scheme_name else None,
        "annual_plan_status": annual_plan_status,
        "scheme_remarks": scheme_remarks.strip() if scheme_remarks else None,
    }

def edit_delete_section(records, maps, supabase, user, master):
    if user["role"] not in ["superadmin", "district"]: return
    if not records:
        st.info("No records available to manage.")
        return

    st.markdown("#### 🔍 Advanced Search & Filter")
    
    block_ids = list(set(r.get("block_id") for r in records if r.get("block_id")))
    block_names = sorted(list(set(maps["block_reverse"].get(b, "Unknown") for b in block_ids)))
    
    dept_ids = list(set(r.get("department_id") for r in records if r.get("department_id")))
    dept_names = sorted(list(set(maps["dept_reverse"].get(d, "Unknown") for d in dept_ids)))

    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        sel_block = col1.selectbox("Filter by Block", ["All"] + block_names)
        sel_dept = col2.selectbox("Filter by Department", ["All"] + dept_names)
        
        # -- UPDATED: Dynamic GP Query from DB --
        if sel_block != "All":
            block_id = maps["block_map"].get(sel_block)
            if block_id:
                res = supabase.table("gps").select("gp_name").eq("block_id", block_id).eq("active", True).execute()
                gp_names = sorted([r['gp_name'] for r in res.data])
            else:
                gp_names = []
        else:
            gps = set()
            for r in records:
                loc = r.get("geo_location", "")
                if "GP:" in loc:
                    try:
                        gp_part = loc.split("GP:")[1].split("|")[0].strip()
                        if gp_part: gps.add(gp_part)
                    except: pass
            gp_names = sorted(list(gps))

        sel_gp = col3.selectbox("Filter by GP", ["All"] + gp_names)
        search_text = col4.text_input("Search Activity / Work Name", placeholder="Type to search...")
    
    filtered_records = records
    if sel_block != "All":
        block_id = maps["block_map"].get(sel_block)
        filtered_records = [r for r in filtered_records if r.get("block_id") == block_id]
    if sel_dept != "All":
        dept_id = maps["dept_map"].get(sel_dept)
        filtered_records = [r for r in filtered_records if r.get("department_id") == dept_id]
    if sel_gp != "All":
        filtered_records = [r for r in filtered_records if sel_gp in r.get("geo_location", "")]
    if search_text:
        filtered_records = [r for r in filtered_records if search_text.lower() in r.get("activity_description", "").lower()]
    
    if not filtered_records:
        st.warning("No activities match the selected filters.")
        return

    st.markdown("---")
    st.markdown("#### 🛠️ Modify Selected Activity")
    
    display_options = {
        r["id"]: f"{r['activity_description']} - {maps['dept_reverse'].get(r['department_id'], 'Unknown')} (₹{r.get('total_converged_fund', 0)} L)"
        for r in filtered_records
    }
    
    selected_edit_id = st.selectbox(
        "Select Activity to Modify",
        options=list(display_options.keys()),
        format_func=lambda x: display_options[x]
    )
    
    if not selected_edit_id: return
    rec = next(r for r in filtered_records if r["id"] == selected_edit_id)

    if st.button("🗑️ Permanently Delete Activity", type="primary"):
        try:
            supabase.table("convergence_register").delete().eq("id", selected_edit_id).execute()
            try: log_action(user.get("id"), f"DELETE convergence_register {selected_edit_id}")
            except: pass
            st.success("Activity deleted successfully!")
            st.rerun()
        except Exception as e: st.error(f"Error deleting record: {e}")

    with st.form("edit_conv_form"):
        col_e1, col_e2 = st.columns(2)
        current_status = rec.get("current_status", "Planned")
        new_status = col_e1.selectbox("Status", STATUS_OPTIONS, index=STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0)
        current_conv = rec.get("convergence_type", CONVERGENCE_TYPES[0])
        new_conv_type = col_e2.selectbox("Convergence Type", CONVERGENCE_TYPES, index=CONVERGENCE_TYPES.index(current_conv) if current_conv in CONVERGENCE_TYPES else 0)

        curr_pia = rec.get("pia_type", "Select PIA")
        pia_index = PIA_OPTIONS.index(curr_pia) if curr_pia in PIA_OPTIONS else 0
        new_pia = st.selectbox("Project Implementing Agency (PIA)*", PIA_OPTIONS, index=pia_index)

        # ---- NEW: Wing selection for edit ----
        dept_id = rec.get("department_id")
        dept_wings = [w for w in master["wings"] if w["department_id"] == dept_id]
        wing_choices = [("Direct Parent Department", None)] + [(w["wing_name"], w["id"]) for w in dept_wings]
        wing_labels = [label for label, _ in wing_choices]
        wing_ids = [wid for _, wid in wing_choices]
        current_wing_id = rec.get("wing_id")
        default_idx = wing_ids.index(current_wing_id) if current_wing_id in wing_ids else 0
        selected_wing_label = st.selectbox(
            "Entering Wing / Scheme Source",
            options=wing_labels,
            index=default_idx
        )
        new_wing_id = wing_ids[wing_labels.index(selected_wing_label)]

        # ---- MODIFIED: Edit Base Activity using Dropdown ----
        mapped_act_ids_edit = [m["activity_id"] for m in master["act_dept_mapping"] if m["department_id"] == dept_id]
        valid_activities_edit = [a for a in master["activities"] if a["id"] in mapped_act_ids_edit]
        valid_act_names_edit = [a["activity_name"] for a in valid_activities_edit]
        
        current_desc = rec.get("activity_description", "")
        current_base_act = current_desc.split(" at ", 1)[0].strip() if " at " in current_desc else current_desc
        
        default_index = 0
        if current_base_act in valid_act_names_edit:
            default_index = valid_act_names_edit.index(current_base_act)
        
        new_base_act = st.selectbox("Base Activity*", valid_act_names_edit, index=default_index)
        
        # --- REMOVED PERMISSIBILITY CHECK ---

        new_geo = st.text_input("Location Details & GP Mapping", value=rec.get("geo_location", "") or "")
        new_work_name = f"{new_base_act} at {new_geo}" if new_geo else new_base_act
        st.text_input("Final Work Name (Auto-generated)", value=new_work_name, disabled=True)
        # -------------------------------------

        new_outcome = st.text_area("Possible Outcome / Work Dimensions", value=rec.get("work_dimensions", "") or "")

        col_det5, col_det6 = st.columns(2)
        new_mis = col_det5.text_input("MIS Code", value=rec.get("mis_code", "") or "")
        curr_origin = rec.get("origin_source", "District Plan")
        new_origin = col_det6.selectbox("Source of Activity", ORIGIN_SOURCES, index=ORIGIN_SOURCES.index(curr_origin) if curr_origin in ORIGIN_SOURCES else 0)

        col_t1, col_t2 = st.columns(2)
        new_d_fund = col_t1.number_input("Department Fund (₹ Lakhs)", value=float(rec.get("department_fund", 0.0)))
        new_v_fund = col_t2.number_input("VB-G RAM G Fund (₹ Lakhs)", value=float(rec.get("vbgramg_fund", 0.0)))
        new_pd = st.number_input("Expected Persondays*", value=int(rec.get("expected_persondays", 0)))

        st.markdown("---")
        defaults = {
            "convergence": rec.get("department_scheme_convergence", False),
            "scheme_name": rec.get("department_scheme_name", "") or "",
            "annual_plan_status": rec.get("department_annual_plan_status", "Not Confirmed"),
            "scheme_remarks": rec.get("department_scheme_remarks", "") or "",
        }
        scheme_data = render_scheme_convergence_section(defaults, key_prefix="edit")

        if st.form_submit_button("Commit Changes", type="primary"):
            errors = []
            if new_conv_type == "Technical Convergence (Zero Fund/NOC)":
                new_d_fund = new_v_fund = 0.0
            if new_pia == "Select PIA":
                errors.append("⚠️ Please select a valid Project Implementing Agency (PIA).")
            elif scheme_data["convergence"] and not scheme_data["scheme_name"]:
                errors.append("⚠️ Scheme / Fund name is mandatory when Convergence = Yes.")
            elif new_conv_type != "Technical Convergence (Zero Fund/NOC)" and new_d_fund == 0.0 and new_v_fund == 0.0:
                errors.append("⚠️ Financial Convergence requires a Fund amount > 0.")
            elif new_pd <= 0:
                errors.append("⚠️ Expected Persondays is mandatory and must be greater than zero.")

            if errors:
                for err in errors: st.error(f"⚠️ {err}")
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
                    "pia_type": new_pia,
                    "wing_id": new_wing_id,
                    "activity_id": selected_act_edit_rec["id"] if selected_act_edit_rec else None, # <-- Preserved activity_id
                    "department_scheme_convergence": scheme_data["convergence"],
                    "department_scheme_name": scheme_data["scheme_name"],
                    "department_annual_plan_status": scheme_data["annual_plan_status"],
                    "department_scheme_remarks": scheme_data["scheme_remarks"],
                }
                try:
                    supabase.table("convergence_register").update(update_payload).eq("id", selected_edit_id).execute()
                    try: log_action(user.get("id"), f"UPDATE convergence_register {selected_edit_id}")
                    except: pass
                    st.success("Activity updated successfully!")
                    st.rerun()
                except Exception as e: st.error(f"Error updating record: {e}")

# ---------- MAIN UI ----------
def show():
    require_role("superadmin", "district", "block", "department")
    user = get_current_user()
    role = user["role"]
    supabase = get_supabase()

    master = fetch_master_lookups()
    maps = build_maps(master)

    if not master["fys"]:
        st.error("⚠️ No active Financial Years found in the database. Please contact your administrator to add a Financial Year.")
        st.stop()

    records = get_filtered_records(supabase, role, user)
    df_records = pd.DataFrame(records) if records else pd.DataFrame()
    exact_count = get_record_count(supabase, role, user)

    render_kpi_cards(df_records, exact_count)

    tab_list = [
        "📋 Master Work Register",
        "➕ Add New Activity"
    ]
    if role in ["superadmin", "district"]:
        tab_list.append("🛠️ Manage / Amend Activity")

    tabs = st.tabs(tab_list)

    with tabs[0]:
        display_register(df_records, maps)

    with tabs[1]:
        st.markdown("#### ➕ Register Individual Convergence Activity")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            fy_id_options = list(maps["fy_reverse"].keys())
            selected_fy_id = col1.selectbox("Financial Year*", options=fy_id_options, format_func=lambda x: maps["fy_reverse"][x])

            dept_options = [{"label": f"{d['department_name']} (Main Dept)", "dept_id": d['id'], "wing_id": None} for d in master["depts"]]
            for w in master["wings"]:
                p_name = maps["dept_reverse"].get(w["department_id"], "Unknown")
                dept_options.append({"label": f"{p_name} ➔ {w['wing_name']} [{w['entity_type']}]", "dept_id": w['department_id'], "wing_id": w['id']})
            dept_options = sorted(dept_options, key=lambda x: x['label'])
            dept_labels = [opt['label'] for opt in dept_options]

            if role == "department":
                user_dept_id, user_wing_id = user.get("department_id"), user.get("wing_id")
                preselected_dept = next((opt for opt in dept_options if opt['dept_id'] == user_dept_id and opt['wing_id'] == user_wing_id), None)
                if preselected_dept:
                    sel_dept_label = col2.selectbox("Department / Wing*", [preselected_dept["label"]], disabled=True)
                    selected_opt = preselected_dept
                else:
                    sel_dept_label = col2.selectbox("Department / Wing*", dept_labels)
                    selected_opt = next(opt for opt in dept_options if opt['label'] == sel_dept_label)
            else:
                sel_dept_label = col2.selectbox("Department / Wing*", dept_labels)
                selected_opt = next(opt for opt in dept_options if opt['label'] == sel_dept_label)

            selected_dept_id = selected_opt['dept_id']
            selected_wing_id = selected_opt['wing_id']

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

            st.markdown("##### 📍 Gram Panchayat (GP) & Spatial Details")
            
            # -- UPDATED: Dynamic GP Query from DB --
            block_id = maps["block_map"].get(sel_block) if sel_block != "Select Block" else None
            gps_in_block = []
            if block_id:
                res = supabase.table("gps").select("gp_name").eq("block_id", block_id).eq("active", True).execute()
                gps_in_block = [r['gp_name'] for r in res.data]
                
            gp_options = ["Select GP"] + sorted(gps_in_block) if sel_block != "Select Block" else ["Select GP"]
            # ---------------------------------------

            col_gp1, col_gp2, col_gp3 = st.columns(3)
            primary_gp = col_gp1.selectbox("Primary Gram Panchayat (GP)*", gp_options)
            has_add_gp = col_gp2.selectbox("Additional GP Covered?", ["No", "Yes"])
            additional_gp, add_gp_portion = "", ""
            if has_add_gp == "Yes":
                additional_gp = col_gp2.selectbox("Additional GP Name", gp_options)
                add_gp_portion = col_gp3.text_input("Portion in Addl. GP", placeholder="e.g. 2 km or 40%")

            st.markdown("##### 🏛️ Project Implementing Agency (PIA)")
            selected_pia = st.selectbox("Implementing Agency (PIA)*", PIA_OPTIONS)

            st.markdown("##### 🏗️ Thematic Work Category & Linkage")
            mapped_act_ids = [m["activity_id"] for m in master["act_dept_mapping"] if m["department_id"] == selected_dept_id]
            valid_activities = [a for a in master["activities"] if a["id"] in mapped_act_ids]
            valid_act_names = [a["activity_name"] for a in valid_activities]

            col_act1, col_loc1 = st.columns(2)
            
            # REMOVED PERMISSIBILITY CHECKS
            if not valid_act_names:
                st.warning(f"No approved activities found for {sel_dept_label}.")
                sel_act_name = col_act1.selectbox("Base Activity*", ["No activities available"], disabled=True)
            else:
                sel_act_name = col_act1.selectbox("Base Activity*", valid_act_names)
                selected_act_record = next((a for a in valid_activities if a["activity_name"] == sel_act_name), None)

            inp_loc_details = col_loc1.text_input("Location Details*", placeholder="Village / Beneficiary Name / Chainage")
            auto_desc = f"{sel_act_name} at {inp_loc_details}" if sel_act_name and sel_act_name != "No activities available" and inp_loc_details else ""

            col_wn, col_ll = st.columns(2)
            
            # ---- MODIFIED: Locking the Work Name Input ----
            with col_wn:
                st.text_input("Work Name (Auto-generated)", value=auto_desc, disabled=True)
            final_work_name = auto_desc  # Strictly enforce this for insertion
            # ----------------------------------------------

            inp_lat_long = col_ll.text_input("Latitude & Longitude (Optional)", placeholder="e.g. 22.89, 88.01")

            sel_conv_type = st.selectbox("Type of Convergence*", CONVERGENCE_TYPES)

            st.markdown("##### 🎯 Targets & Financial Allocation")
            col_f1, col_f2 = st.columns(2)

            if role == "district":
                dist_name = maps["dist_reverse"].get(user.get("district_id"), "District")
                origin_options = ["District Annual Action Plan", f"District Meeting ({dist_name})"]
            elif role == "block":
                block_name = maps["block_reverse"].get(user.get("block_id"), "Block")
                origin_options = ["Block Annual Action Plan", f"Block Meeting ({block_name})"]
            else:
                origin_options = ["District Plan", "Block Plan", "District Meeting", "Block Meeting"]
            
            inp_origin = col_f1.selectbox("Source of Activity Linkage", origin_options)

            persondays = col_f2.number_input("Expected Persondays*", min_value=0)
            possible_outcome = st.text_area("Expected Deliverables / Outcome", placeholder="e.g. 50 farmers benefited, 1 AWC constructed")

            if sel_conv_type == "Technical Convergence (Zero Fund/NOC)":
                st.info("ℹ️ Technical Convergence selected: Fund involvement is automatically 0.0.")
                dept_fund = vbg_fund = 0.0
            else:
                col_f3, col_f4 = st.columns(2)
                dept_fund = col_f3.number_input("Department Fund (₹ Lakhs)", min_value=0.0, step=0.1)
                vbg_fund = col_f4.number_input("VB-G RAM G Fund (₹ Lakhs)", min_value=0.0, step=0.1)

            st.markdown("---")
            scheme_defaults = {"convergence": False, "scheme_name": "", "annual_plan_status": "Not Confirmed", "scheme_remarks": ""}
            scheme_data = render_scheme_convergence_section(scheme_defaults, key_prefix="new")

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Commit Activity Registration", type="primary", use_container_width=True):
                errors = []
                # REMOVED PERMISSIBILITY ERROR CHECK
                if selected_pia == "Select PIA": errors.append("Please select a valid Project Implementing Agency (PIA).")
                if not valid_act_names: errors.append("Approved activity required.")
                if sel_block == "Select Block": errors.append("Please select a valid Block.")
                if primary_gp == "Select GP": errors.append("Primary GP is mandatory.")
                if has_add_gp == "Yes" and additional_gp == "Select GP": errors.append("Please choose a valid Additional GP Name.")
                if not inp_loc_details.strip(): errors.append("Location Details are mandatory.")
                if not final_work_name.strip(): errors.append("Work Name is mandatory.")
                if sel_conv_type != "Technical Convergence (Zero Fund/NOC)" and dept_fund == 0.0 and vbg_fund == 0.0:
                    errors.append("Financial Convergence requires a Fund allocation.")
                if persondays <= 0: errors.append("Expected Persondays must be greater than zero.")
                if scheme_data["convergence"] and not scheme_data["scheme_name"]: errors.append("Scheme / Fund name is mandatory when Convergence = Yes.")

                if errors:
                    for err in errors: st.error(f"⚠️ {err}")
                else:
                    block_id = maps["block_map"].get(sel_block)
                    geo_string = f"Loc: {inp_loc_details} | GP: {primary_gp}"
                    if has_add_gp == "Yes" and additional_gp and additional_gp != "Select GP":
                        geo_string += f" | Addl GP: {additional_gp} (Portion: {add_gp_portion})"
                    if inp_lat_long: geo_string += f" | GPS: {inp_lat_long}"

                    duplicate_check = supabase.table("convergence_register").select("id")\
                        .eq("financial_year_id", selected_fy_id)\
                        .eq("block_id", block_id)\
                        .eq("department_id", selected_dept_id)\
                        .eq("activity_description", final_work_name)\
                        .eq("geo_location", geo_string).execute()
                    
                    if len(duplicate_check.data) > 0:
                        st.error(f"⛔ Duplicate Work Detected! This exact activity (Block, Dept, Work Name, and Location) already exists in the register.")
                    else:
                        insert_data = {
                            "financial_year_id": selected_fy_id, "district_id": selected_dist_id, "block_id": block_id,
                            "department_id": selected_dept_id, "wing_id": selected_wing_id,
                            "pia_type": selected_pia,
                            "activity_description": final_work_name, 
                            "activity_id": selected_act_record["id"] if selected_act_record else None, # <-- preserved activity_id, removed thematic_category_id
                            "convergence_type": sel_conv_type, "scheme_name": None, "geo_location": geo_string,
                            "work_dimensions": possible_outcome, "dimension_unit": "Outcome", "origin_source": inp_origin,
                            "desired_target": 1, "expected_persondays": persondays, "department_fund": dept_fund,
                            "vbgramg_fund": vbg_fund, "current_status": "Planned",
                            "department_scheme_convergence": scheme_data["convergence"],
                            "department_scheme_name": scheme_data["scheme_name"],
                            "department_annual_plan_status": scheme_data["annual_plan_status"],
                            "department_scheme_remarks": scheme_data["scheme_remarks"],
                        }
                        try:
                            res = supabase.table("convergence_register").insert(insert_data).execute()
                            try: log_action(user.get("id"), f"CREATE convergence_register {res.data[0]['id']}")
                            except: pass
                            st.success("✅ Convergence activity successfully created and registered!")
                            st.rerun()
                        except Exception as e:
                            check_res = supabase.table("convergence_register").select("id").eq("activity_description", final_work_name).execute()
                            if check_res.data and len(check_res.data) > 0:
                                st.success("✅ Convergence activity successfully created and registered!")
                                st.rerun()
                            else:
                                st.error(f"Error saving record: {e}")

    if len(tabs) > 2:
        with tabs[2]:
            edit_delete_section(records, maps, supabase, user, master)

    # Fixed footer into a single line to prevent syntax errors
    st.markdown("<div style='text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #E2E8F0; color: #64748B; font-size: 14px; font-weight: 600;'>Hooghly District Administration || District VB GRAM G Cell || Mail : nodal.hooghly@gmail.com</div>", unsafe_allow_html=True)
