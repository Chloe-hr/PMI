"""Reusable visual and comparison components for the PMI decision workspace."""
from html import escape
import textwrap
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from research.ifc4d.viewer_ui import geometry_figure

NAVY="#0A2035"
BLUE="#1F4E9E"
GOLD="#EBAE38"
PHASE_COLORS=["#447EB9","#00A8AA","#677BB5","#D97963","#689689","#9C83AA","#B08A52"]
PROJECT_NAMES={"SYN-BRG-001":"Bridge","SYN-BLD-001":"Mid-rise Building"}
VERSION_NAMES={"V0":"Baseline","V1":"Revision 1","V2":"Revision 2"}
SCHEDULE_NAMES={"as_provided":"Original Schedule","derived":"Recalculated Schedule"}
PRIORITIES={
    "Economic priority":("Cost-aware decisions","Compare construction costs and the cost of schedule disruption.","Requires verified rates, quantities and a cost estimator."),
    "Feasibility priority":("Buildable programmes","Assess crews, access, sequencing and delivery constraints.","Requires resource calendars, constraints and feasibility checks."),
    "Environmental priority":("Lower-impact choices","Compare material and construction-stage environmental impacts.","Requires material inventories, factors and an emissions estimator."),
}


def apply_style():
    st.markdown("""<style>
    .stApp {background:#FFFFFF;color:#172B40;font-family:'Segoe UI',Arial,sans-serif;}
    .block-container {padding-top:1.2rem;padding-bottom:4rem;max-width:1920px;}
    h1,h2,h3 {color:#0A2035;letter-spacing:-.02em;}
    h1 {font-size:2rem!important;} h2 {font-size:1.6rem!important;} h3 {font-size:1.13rem!important;}
    p, label {font-size:1rem;} [data-testid="stCaptionContainer"] {color:#536579;}
    div:has(> .st-key-pmi_controls) {position:sticky;top:3.5rem;z-index:20;background:white;}
    .st-key-pmi_controls {background:white;border-bottom:1px solid #E3EAF1;padding:0 0 .6rem;}
    h2,h3 {scroll-margin-top:150px;}
    [data-testid="stMetricValue"] {font-size:1.65rem;color:#1F4E9E;}
    .pmi-eyebrow {font-size:.72rem;font-weight:700;letter-spacing:.12em;color:#447EB9;text-transform:uppercase;margin-bottom:.25rem;}
    .pmi-lead {font-size:1rem;color:#536579;margin:0;}
    .pmi-tag {display:inline-block;background:#EEF4FA;border:1px solid #DCE6F1;border-radius:20px;padding:5px 12px;font-size:.78rem;color:#24466B;}
    .pmi-phase-legend {display:flex;gap:12px;flex-wrap:wrap;margin:5px 0 10px;font-size:.8rem;color:#30465C;}
    .pmi-dot {display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px;}
    .pmi-callout {padding:15px 18px;border-left:3px solid #00A8AA;background:#F3F8FB;border-radius:0 8px 8px 0;color:#30465C;}
    .pmi-section {border-top:1px solid #E3EAF1;padding-top:23px;margin-top:28px;}
    .pmi-card {min-height:195px;border:1px solid #DDE6EF;border-radius:12px;padding:22px;background:#FFFFFF;}
    .pmi-card h3 {margin:14px 0 8px;font-size:1.1rem;}.pmi-card p {color:#536579;font-size:.9rem;line-height:1.5;}
    .pmi-card small {display:block;color:#536579;margin-top:15px;line-height:1.5;}
    .pmi-final {padding:26px;border:1px dashed #B6C8DA;border-radius:12px;background:#F8FAFC;}
    </style>""",unsafe_allow_html=True)


def section(number,title,description):
    st.markdown(f'<div class="pmi-section"><div class="pmi-eyebrow">{escape(number)}</div></div>',unsafe_allow_html=True)
    st.subheader(title)
    st.caption(description)


def phase_map(bundle,project):
    return {r["task_id"]:r["work_package"] for r in bundle["records"]["Activities"] if r["project_id"]==project}


def phase_colors(phases):
    return {phase:PHASE_COLORS[i%len(PHASE_COLORS)] for i,phase in enumerate(dict.fromkeys(phases.values()))}


def phase_legend(colors):
    st.markdown('<div class="pmi-phase-legend">'+''.join(f'<span><i class="pmi-dot" style="background:{color}"></i>{escape(phase)}</span>' for phase,color in colors.items())+'</div>',unsafe_allow_html=True)


def comparison(baseline,revision):
    """Describe snapshot differences only: no causal or geometry-change inference."""
    a=baseline["tasks"].set_index("task_id");b=revision["tasks"].set_index("task_id")
    rows=[]
    for tid in b.index:
        old,new=a.loc[tid],b.loc[tid]
        ds=(pd.Timestamp(new.start)-pd.Timestamp(old.start)).days
        df=(pd.Timestamp(new.finish)-pd.Timestamp(old.finish)).days
        dd=int(new.duration)-int(old.duration)
        if ds or df or dd:
            rows.append(dict(task_id=tid,activity=new.task_name,baseline_start=old.start,revision_start=new.start,
                             baseline_finish=old.finish,revision_finish=new.finish,
                             baseline_duration=int(old.duration),revision_duration=int(new.duration),
                             start_shift=ds,finish_shift=df,duration_change=dd))
    changed={r["task_id"] for r in rows}
    signature=lambda d:(d["predecessor_task_id"],d["successor_task_id"],d["relationship_type"],d["lag_days"])
    before={d["dependency_id"]:signature(d) for d in baseline["dependencies"]}
    after={d["dependency_id"]:signature(d) for d in revision["dependencies"]}
    changed_links={key for key in before.keys()|after.keys() if before.get(key)!=after.get(key)}
    affected=[d for d in revision["dependencies"] if d["predecessor_task_id"] in changed or d["successor_task_id"] in changed]
    return dict(rows=rows,changed_tasks=changed,changed_dependencies=changed_links,affected_dependencies=affected,
                element_ids={gid for tid,gid in revision["links"] if tid in changed},
                finish_shift=(pd.Timestamp(b.finish.max())-pd.Timestamp(a.finish.max())).days)


def schedule_chart(selected,task_id,phases,baseline=None,counterpart=None,observations=None):
    tasks=selected["tasks"];colors=phase_colors(phases);fig=go.Figure()
    def activity_label(name):
        if "zone " in name:
            title,zone=name.rsplit("zone ",1)
            title=title.rstrip(" -"+chr(8212)+chr(8211))
            return title+"<br>Zone "+zone
        return '<br>'.join(textwrap.wrap(name,width=36))
    labels={r.task_id:activity_label(r.task_name) for r in tasks.itertuples()}
    def bars(table,name,ghost=False):
        alerts={c["task_id"] for c in selected["selected_conflicts"]}|{c["predecessor_task_id"] for c in selected["selected_conflicts"]}
        details=[[r.task_id,r.task_name,r.start,r.finish,int(r.duration),phases[r.task_id],r.original_start,r.original_finish,
                  r.derived_start,r.derived_finish,r.start_shift_days,r.finish_shift_days,r.version_id,r.as_of_date,r.representation] for r in table.itertuples()]
        fig.add_bar(y=[r.task_id for r in table.itertuples()],x=table.duration*86400000,base=pd.to_datetime(table.start).tolist(),orientation="h",name=name,
                    marker_color=["#DAE3EF" if ghost else GOLD if tid==task_id else colors[phases[tid]] for tid in table.task_id],
                    marker_line_color=["#B7C8DC" if ghost else "#D64545" if tid in alerts else "#FFFFFF" for tid in table.task_id],
                    marker_line_width=[1 if ghost else 2 if tid in alerts else 0 for tid in table.task_id],opacity=.75 if ghost else 1,
                    customdata=details,hovertemplate="<b>%{customdata[1]}</b><br>%{customdata[5]}<br>%{customdata[2]} to %{customdata[3]} (inclusive)<br>%{customdata[4]} calendar days<br>Original: %{customdata[6]} to %{customdata[7]}<br>Recalculated: %{customdata[8]} to %{customdata[9]}<br>Recalculation shift: start %{customdata[10]}d / finish %{customdata[11]}d<br>Snapshot: %{customdata[12]} | as of %{customdata[13]}<extra>"+name+"</extra>")
    if baseline is not None:
        bars(baseline["tasks"],"Baseline reference",True)
    if counterpart is not None:
        bars(counterpart["tasks"],SCHEDULE_NAMES[counterpart["tasks"].representation.iloc[0]],True)
    bars(tasks,SCHEDULE_NAMES[tasks.representation.iloc[0]])
    if observations:
        fig.add_scatter(x=[r["observation_date"] for r in observations],y=[r["task_id"] for r in observations],mode="markers",
                        name="Synthetic progress",marker=dict(symbol="diamond",size=8,color="#8E579F"),
                        customdata=[[r["task_id"],r["observed_percent_synthetic"]] for r in observations],
                        hovertemplate="Synthetic progress: %{customdata[1]}%<br>Source observation on %{x}<extra></extra>")
    fig.update_layout(height=max(610,len(tasks)*27+100),barmode="group",bargap=.25,clickmode="event+select",
                      font=dict(family="Segoe UI, Arial, sans-serif",size=12,color="#30465C"),paper_bgcolor="white",plot_bgcolor="#F8FAFD",
                      xaxis=dict(type="date",title="Calendar dates",showgrid=True,gridcolor="#E5ECF3",side="top",tickfont=dict(size=12)),
                      yaxis=dict(autorange="reversed",tickmode="array",tickvals=list(labels),ticktext=list(labels.values()),title=None,automargin=True),
                      margin=dict(l=0,r=10,t=45,b=20),legend=dict(orientation="h",y=-.07),
                      uirevision=tasks.project_id.iloc[0]+tasks.version_id.iloc[0]+tasks.representation.iloc[0])
    return fig


def model_chart(meshes,highlighted,scope):
    fig=geometry_figure(meshes,highlighted)
    for trace in fig.data:
        selected=trace.name=="Assigned to selected task"
        trace.name=("Selected activity" if scope=="Selected activity" else "Schedule-affected elements") if selected else "Project model"
        trace.color=GOLD if selected else "#7C9EBE"
        trace.opacity=1 if selected else .4
        trace.hovertemplate="Element linked to schedule<extra></extra>"
    fig.update_layout(height=610,paper_bgcolor="#F8FAFD",font=dict(family="Segoe UI, Arial, sans-serif",size=12,color="#30465C"),
                      scene=dict(xaxis_visible=False,yaxis_visible=False,zaxis_visible=False,aspectmode="data",
                                 camera=dict(eye=dict(x=2.0,y=2.0,z=2.0),projection=dict(type="orthographic"))),legend=dict(orientation="h",y=-.03))
    # Leave room around the actual site extents so an orthographic overview does not crop edge elements.
    vertices=[v for mesh in meshes for v in mesh["vertices"]]
    for index,axis in enumerate(("xaxis","yaxis","zaxis")):
        values=[v[index] for v in vertices]
        lo,hi=min(values),max(values)
        pad=max((hi-lo)*.4,.1)
        fig.update_scenes(**{axis:dict(range=[lo-pad,hi+pad],autorange=False)})
    return fig


def scenario_request(project,snapshot,representation,priority,source_sha256):
    if priority not in PRIORITIES:
        raise ValueError("Unknown scenario priority")
    return dict(project_id=project,snapshot=snapshot,representation=representation,priority=priority,
                schedule_artifact_sha256=source_sha256,status="awaiting_estimators_and_scenario_engine",
                constraints={},engine_run_id=None,final_schedule=None)


def scenario_cards():
    for col,(priority,(title,description,pending)) in zip(st.columns(3,gap="large"),PRIORITIES.items()):
        with col:
            st.markdown(f'<div class="pmi-card"><span class="pmi-tag">Planned capability</span><h3>{escape(priority)}</h3><p>{escape(description)}</p><small>{escape(pending)}</small></div>',unsafe_allow_html=True)
