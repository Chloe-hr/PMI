"""Streamlit IFC4D workspace. Only reads Stage 3.8B artifacts."""
from datetime import date
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from research.ifc4d import viewer_data as data

BLUE="#2879C9"
TEAL="#168A82"
RED="#D64545"
GOLD="#F1AE32"


def gantt_figure(selected,task_id,compare=True,observations=None):
    tasks=selected["tasks"]
    fig=go.Figure()
    affected={r["task_id"] for r in selected["source_conflicts"]}|{r["predecessor_task_id"] for r in selected["source_conflicts"]}
    current=tasks.representation.iloc[0]
    reps=["as_provided","derived"] if compare else [current]
    for rep in reps:
        source=rep=="as_provided"
        starts=tasks.original_start if source else tasks.derived_start
        finishes=tasks.original_finish if source else tasks.derived_finish
        colors=[GOLD if tid==task_id else RED if source and tid in affected else BLUE if source else TEAL for tid in tasks.task_id]
        custom=[[r.task_id,r.task_name,s,f,r.duration,r.original_start,r.original_finish,r.derived_start,r.derived_finish,
                 r.start_shift_days,r.finish_shift_days,r.project_id,r.version_id,r.as_of_date,rep]
                for r,s,f in zip(tasks.itertuples(),starts,finishes)]
        fig.add_bar(y=tasks.task_id+" | "+tasks.task_name,x=tasks.duration*86400000,
                    base=pd.to_datetime(starts).tolist(),orientation="h",name="Source | as provided" if source else "Derived | computed",
                    marker_color=colors,marker_line_color="#563B09" if rep==current else "#FFFFFF",
                    marker_line_width=2 if rep==current else 0,opacity=1 if rep==current else 0.5,
                    customdata=custom,
                    hovertemplate="<b>%{customdata[0]}</b> | %{customdata[1]}<br>%{customdata[14]} | SYNTHETIC<br>Inclusive: %{customdata[2]} | %{customdata[3]} (%{customdata[4]} calendar days)<br>Source: %{customdata[5]} | %{customdata[6]}<br>Derived: %{customdata[7]} | %{customdata[8]}<br>Start / finish shift: %{customdata[9]} / %{customdata[10]} days<br>%{customdata[11]} | %{customdata[12]} | as of %{customdata[13]}<extra></extra>")
    if observations:
        labels=dict(zip(tasks.task_id,tasks.task_id+" | "+tasks.task_name))
        fig.add_scatter(x=[r["observation_date"] for r in observations],y=[labels[r["task_id"]] for r in observations],
                        mode="markers",name="Synthetic progress | source calendar",marker=dict(symbol="diamond",size=9,color="#A34CB3"),
                        customdata=[[r["task_id"],r["observed_percent_synthetic"],r["observation_date"]] for r in observations],
                        hovertemplate="%{customdata[0]}<br>SYNTHETIC progress: %{customdata[1]}%<br>Source observation date: %{customdata[2]}<extra></extra>")
    fig.update_layout(barmode="group",height=max(630,len(tasks)*30+140),
                      xaxis=dict(type="date",title="Calendar dates | bar ends are exclusive midnight boundaries"),
                      yaxis=dict(autorange="reversed",title=None),clickmode="event+select",
                      margin=dict(l=0,r=10,t=10,b=50),legend=dict(orientation="h",y=1.08),
                      font=dict(size=11),plot_bgcolor="#F5F8FC",uirevision=current+tasks.version_id.iloc[0])
    return fig


def geometry_figure(meshes,highlighted):
    fig=go.Figure()
    for selected in (False,True):
        vertices=[];faces=[];ids=[]
        for mesh in meshes:
            if (mesh["global_id"] in highlighted)!=selected:
                continue
            offset=len(vertices);vertices+=mesh["vertices"]
            faces += [[a+offset,b+offset,c+offset] for a,b,c in mesh["faces"]]
            ids += [[mesh["global_id"],mesh["name"]]]*len(mesh["vertices"])
        if not vertices:
            continue
        x,y,z=zip(*vertices);i,j,k=zip(*faces)
        fig.add_mesh3d(x=x,y=y,z=z,i=i,j=j,k=k,color=GOLD if selected else "#93ADC8",
                       opacity=1 if selected else 0.23,flatshading=True,
                       name="Assigned to selected task" if selected else "Other synthetic elements",showlegend=True,
                       customdata=ids,hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra></extra>")
    fig.update_layout(height=470,scene=dict(aspectmode="data",xaxis_title="X (m)",yaxis_title="Y (m)",zaxis_title="Z (m)"),
                      margin=dict(l=0,r=0,t=0,b=0),legend=dict(orientation="h"),uirevision="ifc4d-camera")
    return fig


@st.cache_data(show_spinner=False)
def cached_meshes(path,verified_sha256):
    return data.meshes(Path(path))


def render(root):
    st.title("PMI | IFC4D schedule explorer")
    st.markdown("**Synthetic construction scenarios** | Geometry, tasks and schedule validation in one view.")
    st.caption("Stage 3.8B preserved artifacts | Calendar days | No predictions or optimization")
    try:
        bundle=data.load_bundle(root/"data/processed/ifc4d/stage3_8b_v1")
    except data.ArtifactError as exc:
        st.error(f"IFC4D artifacts rejected: {exc}")
        st.stop()
    a,b,c=st.columns([1.2,1,1.4])
    project=a.selectbox("Project",data.PROJECTS,key="ifc4d_project")
    snapshot=b.selectbox("Snapshot",data.SNAPSHOTS,key="ifc4d_snapshot")
    rep=c.selectbox("Representation",data.REPRESENTATIONS,key="ifc4d_rep",format_func=lambda x:"As provided | original dates" if x=="as_provided" else "Derived | synthetic computed dates")
    selected=data.select(bundle,project,snapshot,rep)
    taskids=selected["tasks"].task_id.tolist()
    names=selected["tasks"].set_index("task_id").task_name.to_dict()
    if st.session_state.get("ifc4d_task") not in taskids:
        st.session_state.ifc4d_task=taskids[0]
    def task_changed():
        st.session_state.ifc4d_element=None
    def gantt_changed():
        event=st.session_state.get("ifc4d_gantt_event",{})
        points=event.get("selection",{}).get("points",[])
        if points:
            tid=points[-1].get("customdata",[None])[0]
            if tid in taskids:
                st.session_state.ifc4d_task=tid
                st.session_state.ifc4d_element=None
    task=st.selectbox("Selected task",taskids,key="ifc4d_task",format_func=lambda t:t+" | "+names[t],on_change=task_changed)
    try:
        model_meshes=cached_meshes(str(selected["path"]),selected["sha256"])
        data.require({m["global_id"] for m in model_meshes}==set(selected["elements"].ifc_global_id),"Missing IFC geometry")
    except Exception as exc:
        st.error(f"IFC geometry cannot be rendered: {exc}")
        st.stop()
    metrics=st.columns(4)
    metrics[0].metric("Schedule tasks",len(taskids))
    metrics[1].metric("Assigned elements",len(selected["links"]))
    metrics[2].metric("Source FS conflicts",len(selected["source_conflicts"]))
    metrics[3].metric("Selected schedule", "Compliant" if selected["compliant"] else "Has conflicts")
    st.success("IFC round-trip preservation: passed. Source schedule validity is assessed separately.")
    if not selected["compliant"]:
        st.warning("As-provided dates contain finish-to-start conflicts. They are displayed unchanged.")
    else:
        st.info("Derived dates are dependency-compliant synthetic calculations. They are not observations or a resource-feasible forecast.")
    compare=st.checkbox("Compare source and derived dates",value=True)
    progress=st.checkbox("Synthetic progress layer | source calendar",value=False)
    observations=[]
    if progress:
        records=[r for r in bundle["records"]["Progress"] if r["project_id"]==project]
        dates=sorted({r["observation_date"] for r in records})
        cutoff=st.date_input("Synthetic progress as of",value=date.fromisoformat(dates[len(dates)//2]),min_value=date.fromisoformat(dates[0]),max_value=date.fromisoformat(dates[-1]),key="ifc4d_progress_date_"+project)
        for tid in taskids:
            available=[r for r in records if r["task_id"]==tid and r["observation_date"]<=cutoff.isoformat()]
            if available:
                observations.append(max(available,key=lambda r:r["observation_date"]))
        st.caption("Purple diamonds: latest generated record on or before the selected date; no interpolation or projection onto derived dates. Tasks without a record have no progress marker.")
    left,right=st.columns([1.65,1],gap="large")
    with left:
        st.subheader("Construction schedule")
        st.caption("Click a bar to select a task. Gold = selected; red = source-conflict endpoints; blue = source; green = derived. Labels and hover use inclusive finish dates.")
        st.plotly_chart(gantt_figure(selected,task,compare,observations),key="ifc4d_gantt_event",on_select=gantt_changed,selection_mode="points",width="stretch")
    with right:
        st.subheader("IFC geometry")
        highlights=data.task_elements(selected,task)
        st.plotly_chart(geometry_figure(model_meshes,highlights),key="ifc4d_geometry",width="stretch")
        st.caption(f"{len(highlights)} assigned elements highlighted | original IFC GlobalIds | synthetic proxy geometry")
        fallback_count=sum("render_method" in m for m in model_meshes)
        if fallback_count:
            st.caption(f"{fallback_count} exact rectangle extrusions rendered directly from IFC dimensions and placements because the geometry kernel rejected inherited source topology. No IFC values or files were changed.")
        st.caption("Orbit and zoom the model; mesh clicks do not select elements. Use the GlobalId selector below for element-to-task inspection.")
        allgids=sorted(selected["elements"].ifc_global_id)
        if st.session_state.get("ifc4d_element") not in allgids:
            st.session_state.ifc4d_element=None
        def element_changed():
            gid=st.session_state.ifc4d_element
            matches=[tid for tid,element in selected["links"] if element==gid]
            if matches:
                st.session_state.ifc4d_task=matches[0]
        element=st.selectbox("Inspect IFC element (GlobalId)",allgids,index=None,key="ifc4d_element",on_change=element_changed,placeholder="Select an element to inspect its linked task")
        if element:
            st.dataframe(selected["elements"].loc[selected["elements"].ifc_global_id==element].T.astype(str),width="stretch")
            st.write("Linked task:",next(t for t,g in selected["links"] if g==element))
        st.markdown("**Selected task metadata**")
        st.dataframe(selected["tasks"].loc[selected["tasks"].task_id==task].T.astype(str),width="stretch")
        st.markdown("**Assigned IFC GlobalIds**")
        st.code("\n".join(highlights))
    st.subheader("Dependency validation | source versus selected representation")
    st.caption(f"{project} | {snapshot} | {len(selected['source_conflicts'])} source FS conflicts; {len(selected['selected_conflicts'])} selected-representation conflicts. Round-trip preservation does not certify a valid source schedule.")
    conflicts=selected["source_conflicts"]
    if conflicts:
        columns=["dependency_id","predecessor_task_id","task_id","predecessor_finish","successor_start","required_start","shortfall_days","lag_days"]
        st.dataframe(pd.DataFrame(conflicts)[columns].rename(columns={"task_id":"successor_task_id","predecessor_finish":"original_predecessor_finish","successor_start":"original_successor_start"}),hide_index=True,width="stretch")
    else:
        st.write("No source dependency conflicts.")
    with st.expander("Schedule dates, shifts and provenance"):
        st.dataframe(selected["tasks"],hide_index=True,width="stretch")
        st.json(selected["provenance"])
        st.caption("Inherited IFC schema issues: bridge 118; building 167. Stage 3.8B introduced no new schema errors. These fixtures are not schema-clean production exchange models.")
    if progress:
        with st.expander("Synthetic progress records displayed"):
            st.dataframe(pd.DataFrame(observations),hide_index=True,width="stretch")
