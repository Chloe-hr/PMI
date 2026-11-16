"""Professional PMI workspace over immutable Stage 3.8B schedules."""
from datetime import date
from html import escape
import pandas as pd
import streamlit as st
from research.ifc4d import viewer_data as data
from research.ifc4d.viewer_ui import cached_meshes
from research.ifc4d import dashboard_components as ui


def render(root):
    ui.apply_style()
    logo,title=st.columns([1,5],vertical_alignment="center")
    with logo:
        st.image(str(root/"assets/logo/pmi-logo.png"),width=190)
    with title:
        st.markdown('<div class="pmi-eyebrow">Project management intelligence</div><h1 style="margin:0">From change to decision.</h1><p class="pmi-lead">Understand the model. Review the programme. Prepare the next decision.</p>',unsafe_allow_html=True)
    st.caption("Synthetic project demonstration | Schedule comparisons, not observed construction or optimized scenarios")
    try:
        bundle=data.load_bundle(root/"data/processed/ifc4d/stage3_8b_v1")
    except data.ArtifactError as exc:
        st.error(f"Project data could not be verified. Nothing has been displayed. {exc}")
        st.stop()
    with st.container(key="pmi_controls"):
        a,b,c,d=st.columns([1.05,1,1.3,1.8])
        project=a.selectbox("Project",data.PROJECTS,format_func=ui.PROJECT_NAMES.get,key="pmi_project")
        snapshot=b.selectbox("Programme version",data.SNAPSHOTS,format_func=ui.VERSION_NAMES.get,key="pmi_version")
        rep=c.selectbox("Schedule",data.REPRESENTATIONS,format_func=ui.SCHEDULE_NAMES.get,key="pmi_schedule")
        selected=data.select(bundle,project,snapshot,rep)
        ids=selected["tasks"].task_id.tolist();names=selected["tasks"].set_index("task_id").task_name.to_dict()
        if st.session_state.get("pmi_task") not in ids:
            st.session_state.pmi_task=ids[0]
        def task_changed():
            st.session_state.pmi_element=None
        task=d.selectbox("Selected activity",ids,format_func=names.get,key="pmi_task",on_change=task_changed)
    baseline=data.select(bundle,project,"V0","as_provided")
    original=data.select(bundle,project,snapshot,"as_provided")
    changes=ui.comparison(baseline,original)
    phases=ui.phase_map(bundle,project)
    try:
        meshes=cached_meshes(str(selected["path"]),selected["sha256"])
        data.require({m["global_id"] for m in meshes}==set(selected["elements"].ifc_global_id),"Missing model elements")
    except Exception as exc:
        st.error(f"Project model could not be displayed: {exc}")
        st.stop()
    metrics=st.columns(4)
    metrics[0].metric("Programme finish",pd.Timestamp(selected["tasks"].finish.max()).strftime("%d %b %Y"))
    metrics[1].metric("Construction activities",len(ids))
    metrics[2].metric("Activities revised",len(changes["changed_tasks"]))
    metrics[3].metric("Sequence links to review",len(selected["selected_conflicts"]))
    left,right=st.columns([1,1.2],gap="large")
    with left:
        st.subheader("Project model")
        scope=st.radio("Highlight",["Selected activity","Schedule changes"],horizontal=True,key="pmi_highlight")
        highlighted=data.task_elements(selected,task) if scope=="Selected activity" else changes["element_ids"]
        st.plotly_chart(ui.model_chart(meshes,highlighted,scope),width="stretch",key="pmi_model",config={"displaylogo":False})
        st.caption("Gold highlights the linked elements. Orbit or zoom to inspect. Select activities in the programme; direct model-click selection is not available.")
    with right:
        st.subheader("Baseline programme" if snapshot=="V0" else "Baseline & revision programme")
        compare_baseline=False
        if snapshot!="V0":
            compare_baseline=st.checkbox("Show Baseline reference",value=True,key="pmi_baseline_reference")
        ui.phase_legend(ui.phase_colors(phases))
        def select_gantt():
            points=st.session_state.get("pmi_gantt",{}).get("selection",{}).get("points",[])
            if points:
                tid=points[-1].get("customdata",[None])[0]
                if tid in ids:
                    st.session_state.pmi_task=tid;st.session_state.pmi_element=None
        counterpart=None
        compare_recalculated=st.checkbox("Compare original and recalculated dates",key="pmi_compare")
        if compare_recalculated:
            counterpart=data.select(bundle,project,snapshot,"derived" if rep=="as_provided" else "as_provided")
        observations=[]
        progress=st.checkbox("Show synthetic progress",key="pmi_progress")
        if progress:
            records=[r for r in bundle["records"]["Progress"] if r["project_id"]==project]
            dates=sorted({r["observation_date"] for r in records})
            cutoff=st.date_input("Progress date",value=date.fromisoformat(dates[len(dates)//2]),min_value=date.fromisoformat(dates[0]),max_value=date.fromisoformat(dates[-1]),key="pmi_progress_date_"+project)
            for tid in ids:
                available=[r for r in records if r["task_id"]==tid and r["observation_date"]<=cutoff.isoformat()]
                if available:observations.append(max(available,key=lambda r:r["observation_date"]))
            st.caption("Diamonds show generated progress on the source calendar, without interpolation or relocation to recalculated dates.")
        st.plotly_chart(ui.schedule_chart(selected,task,phases,baseline if compare_baseline else None,counterpart,observations),
                        width="stretch",key="pmi_gantt",on_select=select_gantt,selection_mode="points",config={"displaylogo":False})
        st.caption("Click a bar to highlight its elements. Red outlines flag sequence issues. All task dates include their final calendar day.")
    activity=selected["tasks"].set_index("task_id").loc[task]
    with st.container(border=True):
        st.markdown("**Selected activity: "+escape(activity.task_name)+"**")
        x,y,z,w=st.columns(4)
        x.write("**Phase**  "+phases[task]);y.write(f"**Dates**  {activity.start} to {activity.finish}")
        z.write(f"**Duration**  {activity.duration} calendar days");w.write(f"**Linked elements**  {len(data.task_elements(selected,task))}")
        st.caption(f"Recalculation shifts this activity's start by {activity.start_shift_days:+d} and finish by {activity.finish_shift_days:+d} calendar days relative to its original schedule. This is a sequencing calculation, not an optimized outcome.")
    if selected["selected_conflicts"]:
        st.warning(f"{len(selected['selected_conflicts'])} sequence links need review: some activities start before the previous work is due to finish. Original dates are preserved. Inspect the links below.")
    else:
        st.info(f"The recalculated programme satisfies the recorded sequence rules. The original version still has {len(selected['source_conflicts'])} links to review. Resources and site constraints have not been checked.")
    ui.section("04 / Change impact","What changed in the programme?","Compare original schedule snapshots. Model highlighting identifies linked elements, not verified geometry changes.")
    if snapshot=="V0":
        st.write("You are reviewing the Baseline. Choose Revision 1 or Revision 2 above to see changes in dates, durations and affected sequence links.")
    else:
        days=changes["finish_shift"];direction="later" if days>0 else "earlier" if days<0 else "on the same day"
        finish_text=f"{abs(days)} calendar days {direction}" if days else direction
        st.markdown(f'<div class="pmi-callout"><strong>{ui.VERSION_NAMES[snapshot]} vs Baseline.</strong> {len(changes["changed_tasks"])} activities have different dates or durations. The original programme finishes {finish_text}. {len(changes["affected_dependencies"])} sequence links touch these activities; {len(changes["changed_dependencies"])} dependency definitions changed.<br>No geometry change has been established: these snapshots share the same source model.</div>',unsafe_allow_html=True)
        summary=pd.DataFrame(changes["rows"])
        st.dataframe(summary.rename(columns={"activity":"Activity","baseline_start":"Baseline start","revision_start":"Revision start","baseline_finish":"Baseline finish","revision_finish":"Revision finish","baseline_duration":"Baseline days","revision_duration":"Revision days","start_shift":"Start shift (days)","finish_shift":"Finish shift (days)","duration_change":"Duration change (days)"}).drop(columns=["task_id"],errors="ignore"),hide_index=True,width="stretch")
        st.caption("Use Highlight > Schedule changes above to see the model elements linked to these revised activities. Date differences alone do not prove a physical design change or identify its cause.")
    with st.expander("Sequence issues and affected links",expanded=False):
        conflicts=selected["source_conflicts"]
        st.write(f"Original Schedule: {len(conflicts)} links to review. {ui.SCHEDULE_NAMES[rep]}: {len(selected['selected_conflicts'])} links to review.")
        if conflicts:
            table=pd.DataFrame([{"Link":i+1,"Previous activity":names[r["predecessor_task_id"]],"Next activity":names[r["task_id"]],"Previous finish":r["predecessor_finish"],"Original next start":r["successor_start"],"Required next start":r["required_start"],"Shortfall (calendar days)":r["shortfall_days"]} for i,r in enumerate(conflicts)])
            st.dataframe(table,hide_index=True,width="stretch")
        touching=[d for d in selected["dependencies"] if task in (d["predecessor_task_id"],d["successor_task_id"])]
        st.markdown("**Sequence links for the selected activity**")
        st.dataframe(pd.DataFrame([{"Previous activity":names[d["predecessor_task_id"]],"Next activity":names[d["successor_task_id"]],"Rule":"Finish before start","Lag (calendar days)":d["lag_days"]} for d in touching]),hide_index=True,width="stretch")
        if snapshot!="V0":
            st.markdown("**Links touching revision-affected activities**")
            st.dataframe(pd.DataFrame([{"Previous activity":names[d["predecessor_task_id"]],"Next activity":names[d["successor_task_id"]],"Rule":d["relationship_type"],"Lag (days)":d["lag_days"]} for d in changes["affected_dependencies"]]),hide_index=True,width="stretch")
    ui.section("05 / Compare priorities","Choose the questions that matter.","Scenario estimators and the decision engine are planned. No costs, emissions or optimized results are calculated here.")
    ui.scenario_cards()
    priority=st.radio("Planning priority",list(ui.PRIORITIES),horizontal=True,key="pmi_priority")
    request=ui.scenario_request(project,snapshot,rep,priority,selected["sha256"])
    st.session_state.pmi_scenario_request=request
    ui.section("06 / Selected scenario","Final programme","A final scenario programme must be generated from scenario inputs and constraints by the scheduling engine.")
    st.markdown(f'<div class="pmi-final"><span class="pmi-tag">Awaiting scenario engine</span><h3>{escape(priority)}</h3><p>Your planning preference is recorded. No scenario has been evaluated and no final programme has been generated.</p><p>The recalculated schedule above resolves recorded sequencing only. It is not an economic, feasibility or environmental optimum.</p></div>',unsafe_allow_html=True)
    st.button("Generate final programme",disabled=True,help="Available after estimators, scenario constraints and the scheduling-engine adapter are implemented.")
    with st.expander("Technical Details"):
        st.write("Synthetic fixtures only. Round-trip preservation passed independently of source schedule compliance.")
        st.write("Artifact SHA-256:",selected["sha256"])
        st.json(selected["provenance"])
        st.dataframe(selected["tasks"],hide_index=True,width="stretch")
        st.caption("Inherited schema issues: bridge 118, building 167. Source geometry is preserved. Rendering uses the existing exact-extrusion fallback for redundant zero-Z profile coordinates; no IFC file is repaired or rewritten.")
        gids=sorted(selected["elements"].ifc_global_id)
        if st.session_state.get("pmi_element") not in gids:st.session_state.pmi_element=None
        def inspect_element():
            gid=st.session_state.pmi_element
            matches=[tid for tid,element in selected["links"] if element==gid]
            if matches:st.session_state.pmi_task=matches[0]
        element=st.selectbox("Inspect IFC element (GlobalId)",gids,index=None,key="pmi_element",on_change=inspect_element)
        st.code("\n".join(data.task_elements(selected,task)))
        if element:st.dataframe(selected["elements"].loc[selected["elements"].ifc_global_id==element].T.astype(str),width="stretch")
        st.json(selected["source_conflicts"])
        st.json({"manifest_complete":bundle["manifest"]["complete"],"round_trip_passed":bundle["manifest"]["round_trip_passed"]})
        if observations:st.dataframe(pd.DataFrame(observations),hide_index=True,width="stretch")
        st.json(request)
