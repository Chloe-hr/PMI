"""Real desktop-browser acceptance for the PMI dashboard; optional Playwright/Edge."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from research.ifc4d import viewer_data as data
from research.ifc4d import dashboard_components as ui
ROOT=Path(__file__).resolve().parents[2]


def capture(url,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    bundle=data.load_bundle(ROOT/"data/processed/ifc4d/stage3_8b_v1")
    with sync_playwright() as p:
        browser=p.chromium.launch(channel="msedge",headless=True)
        page=browser.new_page(viewport={"width":1920,"height":1400},device_scale_factor=1)
        page.goto(url+"/PMI_Dashboard")
        def ready(project,version="V0",rep="as_provided"):
            page.wait_for_function("""([p,v,r])=>{
                const plots=document.querySelectorAll('.js-plotly-plot');
                const t=plots[1]?.data?.filter(t=>t.type==='bar').at(-1);
                return plots.length===2 && t?.customdata?.[0]?.[0]?.startsWith(p) &&
                       t.customdata[0][12]===p+'-'+v && t.customdata[0][14]===r;
            }""",arg=[project,version,rep],timeout=30000)
            page.get_by_role("heading",name="Final programme",exact=True).wait_for()
            assert page.locator('[data-testid="stException"]').count()==0
        def choose(label,value):
            c=page.get_by_role("combobox",name=label,exact=True)
            c.evaluate("el=>el.scrollIntoView({block:'center',behavior:'instant'})")
            c.focus();c.press("ArrowDown");c.fill(value)
            page.get_by_role("option",name=value,exact=True).click()
        def checkbox(label):
            c=page.get_by_role("checkbox",name=label,exact=True)
            c.focus();c.press("Space")
        def screenshot(name,heading=None):
            if heading:
                page.get_by_role("heading",name=heading,exact=True).evaluate("el=>el.scrollIntoView({block:'start',behavior:'instant'})")
            else:
                page.locator('[data-testid="stMain"]').evaluate("el=>el.scrollTo({top:0,behavior:'instant'})")
            page.mouse.move(10,10)
            page.screenshot(path=str(out/name),full_page=True)
        def selected_mesh_ids():
            return set(page.locator('.js-plotly-plot').first.evaluate("el=>el.data.at(-1).customdata.map(r=>r[0])"))
        ready("SYN-BRG-001")
        # Browser layout checks: separate columns, usable widths, no horizontal overflow.
        boxes=[page.locator('.js-plotly-plot').nth(i).bounding_box() for i in (0,1)]
        assert boxes[0]["x"]+boxes[0]["width"]<boxes[1]["x"]
        assert all(b["width"]>650 for b in boxes)
        assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
        assert page.locator('[data-testid="stMain"]').evaluate("el=>el.scrollWidth<=el.clientWidth")
        assert page.get_by_role("combobox",name="Project",exact=True).input_value()=="Bridge"
        # A real pointer event on Plotly's interaction overlay.
        bar=page.locator('.js-plotly-plot').nth(1).locator('.barlayer .trace').first.locator('.point path').nth(12)
        bar.evaluate("el=>el.scrollIntoView({block:'center',behavior:'instant'})")
        box=bar.bounding_box();page.mouse.click(box["x"]+box["width"]/2,box["y"]+box["height"]/2)
        page.wait_for_function("()=>document.querySelectorAll('.js-plotly-plot')[1]?.data?.filter(t=>t.type==='bar').at(-1).marker.color[12]==='#EBAE38'")
        expected=data.task_elements(data.select(bundle,"SYN-BRG-001","V0","as_provided"),"SYN-BRG-001-T013")
        assert selected_mesh_ids()==set(expected)
        screenshot("bridge_workspace.png")
        choose("Project","Mid-rise Building");ready("SYN-BLD-001")
        choose("Programme version","Revision 2");ready("SYN-BLD-001","V2")
        # Check every visible schedule date against authoritative artifact rows.
        selected=data.select(bundle,"SYN-BLD-001","V2","as_provided")
        actual=page.locator('.js-plotly-plot').nth(1).evaluate("el=>el.data.filter(t=>t.type==='bar').at(-1).customdata.map(r=>[r[0],r[2],r[3],r[4]])")
        assert actual==[[r.task_id,r.start,r.finish,r.duration] for r in selected["tasks"].itertuples()]
        screenshot("building_revision_workspace.png")
        highlight=page.get_by_role("radio",name="Schedule changes",exact=True);highlight.focus();highlight.press("Space")
        changed=ui.comparison(data.select(bundle,"SYN-BLD-001","V0","as_provided"),selected)
        page.wait_for_function("()=>document.querySelectorAll('.js-plotly-plot')[0]?.data?.at(-1).name==='Schedule-affected elements'")
        assert selected_mesh_ids()==changed["element_ids"]
        screenshot("revision_impacts.png","What changed in the programme?")
        page.get_by_text("Sequence issues and affected links",exact=True).click()
        page.get_by_text("Original Schedule: 15 links to review.",exact=False).wait_for()
        screenshot("sequence_issues.png","What changed in the programme?")
        choose("Schedule","Recalculated Schedule");ready("SYN-BLD-001","V2","derived")
        recalculated=data.select(bundle,"SYN-BLD-001","V2","derived")
        actual=page.locator('.js-plotly-plot').nth(1).evaluate("el=>el.data.filter(t=>t.type==='bar').at(-1).customdata.map(r=>[r[0],r[2],r[3],r[4]])")
        assert actual==[[r.task_id,r.start,r.finish,r.duration] for r in recalculated["tasks"].itertuples()]
        checkbox("Compare original and recalculated dates")
        page.wait_for_function("()=>document.querySelectorAll('.js-plotly-plot')[1]?.data?.filter(t=>t.type==='bar').length===3")
        checkbox("Show synthetic progress")
        page.wait_for_function("()=>document.querySelectorAll('.js-plotly-plot')[1]?.data?.some(t=>t.name==='Synthetic progress')")
        screenshot("recalculated_progress.png")
        environmental=page.get_by_role("radio",name="Environmental priority",exact=True)
        environmental.focus();environmental.press("Space")
        assert page.get_by_role("button",name="Generate final programme",exact=True).is_disabled()
        page.wait_for_function("()=>document.querySelector('.pmi-final h3')?.textContent==='Environmental priority'")
        screenshot("scenario_and_final_programme.png","Choose the questions that matter.")
        sticky=page.locator('.st-key-pmi_controls').bounding_box()
        assert 50<=sticky["y"]<=75
        assert page.get_by_role("combobox",name="Project",exact=True).is_visible()
        # Hashes/IDs are accessible but not exposed in the primary workspace.
        technical=page.get_by_text("Technical Details",exact=True)
        technical.click()
        page.get_by_text("Artifact SHA-256:",exact=False).wait_for()
        assert page.locator('[data-testid="stException"]').count()==0
        result=dict(viewport={"width":1920,"height":1400},project_and_version_controls=True,
                    original_and_recalculated_dates_match=True,gantt_pointer_selection=True,
                    exact_task_to_model_highlights=True,revision_affected_model_highlights=True,
                    source_conflicts_visible=15,source_derived_overlay=True,synthetic_progress=True,
                    scenarios_are_pending=True,final_programme_disabled=True,technical_details_accessible=True,
                    direct_mesh_click_selection=False,side_by_side_layout=True,horizontal_overflow=False,
                    sticky_project_version_controls=True,selected_priority_matches_final_placeholder=True,
                    screenshots=6,browser="Microsoft Edge / Playwright")
        (out/"ui_acceptance.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        browser.close();return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",default="http://127.0.0.1:8512")
    parser.add_argument("--out",type=Path,default=ROOT/"research/ifc4d/screenshots/stage3_8c_ux")
    args=parser.parse_args();print(json.dumps(capture(args.url,args.out),indent=2))
