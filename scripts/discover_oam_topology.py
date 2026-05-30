"""
UBB OAM Interconnect Topology Discovery Tool
design by shandouzi

Usage:
    python discover_oam_topology.py <pin_nets_csv> --connectors J1 J2 J3 J4 J5 J6 J7 J8 K1 K2 K3 K4 K5 K6 K7 K8

Algorithm:
    1. Read full pin_nets.csv -> build net_map and comp_map indexes
    2. Filter OAM connector pins by user-specified RefDes
    3. For each OAM net, find AC coupling capacitors on the same net
       (RefDes starts with C, exactly 2 pins, both sides have OAM pins, not power/ground)
    4. Trace through capacitor to find the other OAM endpoint
    5. Output topology_detail.csv, topology_matrix.csv, topology_report.html
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict


POWER_NETS = {"GND", "VCC", "VSS", "GND_EARTH"}


def parse_args():
    p = argparse.ArgumentParser(
        description="UBB OAM Interconnect Topology Discovery Tool"
    )
    p.add_argument(
        "pin_nets_csv",
        help="Path to pin_nets.csv exported by get_component_nets.tcl",
    )
    p.add_argument(
        "--connectors",
        nargs="+",
        required=True,
        help="OAM connector RefDes list, e.g. J1 J2 J3 J4 J5 J6 J7 J8 K1 K2 K3 K4 K5 K6 K7 K8",
    )
    p.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: same as CSV file)",
    )
    p.add_argument(
        "--skip-nets",
        nargs="*",
        default=list(POWER_NETS),
        help="Net names to skip (default: GND VCC VSS)",
    )
    return p.parse_args()


def read_csv(path):
    encodings = ["utf-8-sig", "utf-8", "gb2312", "gbk", "latin-1"]
    for enc in encodings:
        try:
            rows = []
            with open(path, "r", encoding=enc) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append({
                        "refdes": row["RefDes"].strip(),
                        "partvalue": row["PartValue"].strip(),
                        "pinnumber": row["PinNumber"].strip(),
                        "pinname": row["PinName"].strip(),
                        "netname": row["NetName"].strip(),
                        "pagepath": row.get("PagePath", "").strip(),
                    })
            return rows
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise RuntimeError(f"Cannot decode file with any supported encoding: {path}")


def build_indexes(rows):
    net_map = defaultdict(list)
    comp_map = defaultdict(list)
    for r in rows:
        net_map[r["netname"]].append(r)
        comp_map[r["refdes"]].append(r)
    return net_map, comp_map


def find_oam_pins(rows, connector_set):
    oam_pins = []
    for r in rows:
        if r["refdes"] in connector_set:
            oam_pins.append(r)
    return oam_pins


def get_oam_nets(oam_pins, skip_nets):
    nets = set()
    for p in oam_pins:
        nn = p["netname"]
        if nn and nn not in skip_nets:
            nets.add(nn)
    return nets


def find_bridging_caps(net_map, comp_map, oam_nets, connector_set):
    caps = {}
    seen_cap_nets = set()

    for net in oam_nets:
        devices_on_net = net_map.get(net, [])
        for dev in devices_on_net:
            ref = dev["refdes"]
            if not ref.startswith("C"):
                continue
            if ref in connector_set:
                continue

            cap_pins = comp_map.get(ref, [])
            if len(cap_pins) != 2:
                continue

            pin1_net = cap_pins[0]["netname"]
            pin2_net = cap_pins[1]["netname"]

            if pin1_net in POWER_NETS or pin2_net in POWER_NETS:
                continue
            if not pin1_net or not pin2_net:
                continue

            has_oam_side1 = any(
                d["refdes"] in connector_set
                for d in net_map.get(pin1_net, [])
            )
            has_oam_side2 = any(
                d["refdes"] in connector_set
                for d in net_map.get(pin2_net, [])
            )

            if has_oam_side1 and has_oam_side2:
                key = tuple(sorted([pin1_net, pin2_net]))
                if key not in seen_cap_nets:
                    seen_cap_nets.add(key)
                    caps[ref] = {
                        "pin1_net": pin1_net,
                        "pin2_net": pin2_net,
                        "pin1_name": cap_pins[0]["pinname"],
                        "pin2_name": cap_pins[1]["pinname"],
                        "pin1_number": cap_pins[0]["pinnumber"],
                        "pin2_number": cap_pins[1]["pinnumber"],
                        "partvalue": cap_pins[0]["partvalue"],
                    }

    return caps


def trace_topology(caps, net_map, connector_set):
    links = []
    for cap_ref, cap_info in caps.items():
        net_a = cap_info["pin1_net"]
        net_b = cap_info["pin2_net"]

        oam_a_pins = [
            d for d in net_map.get(net_a, [])
            if d["refdes"] in connector_set
        ]
        oam_b_pins = [
            d for d in net_map.get(net_b, [])
            if d["refdes"] in connector_set
        ]

        for pa in oam_a_pins:
            for pb in oam_b_pins:
                if pa["refdes"] == pb["refdes"]:
                    continue
                links.append({
                    "oam_a": pa["refdes"],
                    "pinname_a": pa["pinname"],
                    "pinnumber_a": pa["pinnumber"],
                    "net_a": net_a,
                    "cap_refdes": cap_ref,
                    "cap_partvalue": cap_info["partvalue"],
                    "net_b": net_b,
                    "pinnumber_b": pb["pinnumber"],
                    "pinname_b": pb["pinname"],
                    "oam_b": pb["refdes"],
                })

    return links


def build_matrix(links, connector_list):
    n = len(connector_list)
    idx = {c: i for i, c in enumerate(connector_list)}
    matrix = [[0] * n for _ in range(n)]

    for link in links:
        a = link["oam_a"]
        b = link["oam_b"]
        if a in idx and b in idx:
            matrix[idx[a]][idx[b]] += 1

    return matrix


def write_detail_csv(links, output_path):
    fieldnames = [
        "oam_a", "pinname_a", "pinnumber_a", "net_a",
        "cap_refdes", "cap_partvalue", "net_b",
        "pinnumber_b", "pinname_b", "oam_b",
    ]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(links)


def write_pair_detail_csv(links, oam_map, output_path):
    import re

    def net_sort_key(net):
        m = re.match(r'^(.*[._])(P|N)_(\d+)$', net, re.IGNORECASE)
        if not m:
            return net
        return m.group(1) + m.group(2).upper() + "_" + str(int(m.group(3))).zfill(3)

    pair_map = defaultdict(list)
    for link in links:
        info_a = oam_map.get(link["oam_a"])
        info_b = oam_map.get(link["oam_b"])
        if not info_a or not info_b:
            continue
        lo = min(info_a["oam_idx"], info_b["oam_idx"])
        hi = max(info_a["oam_idx"], info_b["oam_idx"])
        side = info_a["side"] + info_a["side"]
        pair_key = (lo, hi, side)

        lo_ref = link["oam_a"] if info_a["oam_idx"] == lo else link["oam_b"]
        hi_ref = link["oam_b"] if info_a["oam_idx"] == lo else link["oam_a"]

        if info_a["oam_idx"] == lo:
            row = dict(link)
        else:
            row = {
                "oam_a": link["oam_b"], "pinname_a": link["pinname_b"],
                "pinnumber_a": link["pinnumber_b"], "net_a": link["net_b"],
                "cap_refdes": link["cap_refdes"], "cap_partvalue": link["cap_partvalue"],
                "net_b": link["net_a"], "pinnumber_b": link["pinnumber_a"],
                "pinname_b": link["pinname_a"], "oam_b": link["oam_a"],
            }
        row["lo_oam"] = lo
        row["hi_oam"] = hi
        row["side"] = side
        pair_map[pair_key].append(row)

    fieldnames = [
        "lo_oam", "hi_oam", "side",
        "oam_a", "pinnumber_a", "pinname_a", "net_a",
        "cap_refdes", "cap_partvalue",
        "net_b", "pinname_b", "pinnumber_b", "oam_b",
    ]

    all_rows = []
    for key in sorted(pair_map.keys()):
        rows = pair_map[key]
        rows.sort(key=lambda r: net_sort_key(r["net_a"]))
        all_rows.extend(rows)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)


def build_oam_map(connector_list):
    oam_map = {}
    oam_set = set()
    for ref in connector_list:
        prefix = ref[0]
        num = int(ref[1:])
        oam_idx = num
        oam_name = f"OAM{num}"
        oam_map[ref] = {"oam_idx": oam_idx, "oam_name": oam_name, "side": prefix}
        oam_set.add(oam_idx)
    return oam_map, sorted(oam_set)


def build_oam_links(links, oam_map):
    oam_pair_links = defaultdict(list)
    for link in links:
        info_a = oam_map.get(link["oam_a"])
        info_b = oam_map.get(link["oam_b"])
        if not info_a or not info_b:
            continue
        side = info_a["side"] + info_a["side"]
        pair = tuple(sorted([info_a["oam_idx"], info_b["oam_idx"]]))
        oam_pair_links[(pair, side)].append(link)
    return oam_pair_links


def generate_html(links, matrix, connector_list, output_path, stats):
    oam_map, oam_indices = build_oam_map(connector_list)
    oam_pair_links = build_oam_links(links, oam_map)
    num_oams = len(oam_indices)

    oam_summary = {}
    for (pair, side), pair_links in oam_pair_links.items():
        key = f"OAM{pair[0]}_OAM{pair[1]}_{side}"
        oam_summary[key] = {
            "oam_a": pair[0],
            "oam_b": pair[1],
            "side": side,
            "count": len(pair_links),
        }

    links_json = json.dumps(links, ensure_ascii=False)
    oam_map_json = json.dumps(oam_map)
    oam_summary_json = json.dumps(oam_summary)
    stats_json = json.dumps(stats)
    num_oams_json = json.dumps(num_oams)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>UBB OAM Interconnect Topology</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  background: #1a1a2e; color: #e0e0e0;
  font-family: 'Segoe UI', Consolas, monospace;
  padding: 20px;
}}
h1 {{ text-align: center; color: #fff; margin-bottom: 5px; font-size: 20px; }}
.subtitle {{ text-align: center; color: #aaa; margin-bottom: 12px; font-size: 12px; }}
.stats {{
  display: flex; justify-content: center; gap: 14px;
  margin-bottom: 16px; font-size: 12px; flex-wrap: wrap;
}}
.stats span {{ padding: 3px 10px; border-radius: 3px; color: #fff; background: #444; }}

.topo-wrap {{ display: flex; justify-content: center; margin: 10px 0 20px; }}
#topo-svg {{ cursor: default; }}

.oam-node {{ cursor: pointer; }}
.oam-node:hover .oam-circle {{ filter: brightness(1.3); }}
.oam-label {{ font-size: 11px; fill: #fff; font-weight: bold; pointer-events: none; }}
.oam-sub {{ font-size: 8px; fill: #aaa; pointer-events: none; }}
.oam-circle {{ transition: filter 0.15s; }}

.conn-line {{ fill: none; stroke-width: 2.5; cursor: pointer; transition: stroke-width 0.15s, opacity 0.15s; }}
.conn-line:hover {{ stroke-width: 5; opacity: 1 !important; }}
.conn-label {{ font-size: 8px; fill: #ccc; pointer-events: none; text-anchor: middle; }}

.legend {{
  display: flex; justify-content: center; gap: 14px;
  margin: 8px 0 20px; font-size: 11px;
}}
.legend-item {{ display: flex; align-items: center; gap: 3px; }}
.legend-color {{ width: 30px; height: 3px; border-radius: 2px; }}

.tabs {{ display: flex; justify-content: center; gap: 8px; margin-bottom: 16px; }}
.tab-btn {{
  padding: 6px 18px; border: 1px solid #555; background: #2d2d44;
  color: #aaa; border-radius: 4px; cursor: pointer; font-size: 12px;
  font-family: inherit;
}}
.tab-btn.active {{ background: #1565C0; color: #fff; border-color: #1565C0; }}
.tab-btn:hover {{ background: #3a3a5c; }}

.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

.matrix-section {{ margin: 0 0 20px; }}
.matrix-section h2 {{ color: #e0e0e0; font-size: 14px; margin-bottom: 8px; text-align: center; }}
.matrix-wrap {{ display: flex; justify-content: center; overflow-x: auto; }}
.matrix-table {{ border-collapse: collapse; font-size: 11px; }}
.matrix-table th, .matrix-table td {{
  border: 1px solid #333; padding: 4px 6px; text-align: center;
  min-width: 32px; cursor: pointer; transition: background 0.15s;
}}
.matrix-table th {{ background: #2d2d44; color: #fff; }}
.matrix-table td.zero {{ color: #555; cursor: default; }}
.matrix-table td.self {{ background: #1a1a2e; cursor: default; }}
.matrix-table td.val-j {{ color: #42A5F5; font-weight: bold; }}
.matrix-table td.val-k {{ color: #FF9800; font-weight: bold; }}
.matrix-table td:hover {{ outline: 2px solid #81C784; z-index: 1; }}

.detail-section {{ margin: 20px 0; display: none; }}
.detail-section h2 {{ color: #81C784; font-size: 14px; margin-bottom: 8px; text-align: center; }}
.detail-close {{
  display: block; margin: 0 auto 10px; padding: 4px 16px;
  background: #444; color: #fff; border: none; border-radius: 3px;
  cursor: pointer; font-size: 12px;
}}
.detail-close:hover {{ background: #666; }}
.detail-table {{ border-collapse: collapse; font-size: 11px; margin: 0 auto; }}
.detail-table th, .detail-table td {{
  border: 1px solid #333; padding: 4px 8px; text-align: left;
}}
.detail-table th {{ background: #2d2d44; color: #fff; white-space: nowrap; }}
.detail-table tr:nth-child(even) {{ background: #222240; }}
.detail-table tr:hover {{ background: #2d2d55; }}
.detail-filter {{
  text-align: center; margin-bottom: 8px; font-size: 11px;
  display: flex; justify-content: center; gap: 12px;
}}
.detail-filter label {{ display: flex; align-items: center; gap: 3px; cursor: pointer; }}
.detail-filter input {{ cursor: pointer; }}
</style>
</head>
<body>
<h1>UBB OAM Interconnect Topology</h1>
<div class="subtitle">{num_oams} OAM Modules &mdash; {stats["total_links"]} links via {stats["total_caps"]} AC caps</div>
<div class="stats" id="stats-bar"></div>

<div class="tabs">
  <button class="tab-btn active" data-tab="topo">Topology Graph</button>
  <button class="tab-btn" data-tab="matrix">Connection Matrix</button>
</div>

<div class="tab-content active" id="tab-topo">
  <div class="topo-wrap">
    <svg id="topo-svg" width="780" height="780"></svg>
  </div>
  <div class="legend">
    <div class="legend-item"><div class="legend-color" style="background:#42A5F5"></div>CON0 (J-J)</div>
    <div class="legend-item"><div class="legend-color" style="background:#FF9800"></div>CON1 (K-K)</div>
    <div class="legend-item"><span style="font-size:10px;color:#888;">Click line or node for details</span></div>
  </div>
</div>

<div class="tab-content" id="tab-matrix">
  <div class="matrix-section">
  <h2>OAM-to-OAM Connection Count (J=blue, K=orange)</h2>
  <div class="matrix-wrap">
    <table class="matrix-table" id="matrix-table"></table>
  </div>
  </div>
</div>

<div class="detail-section" id="detail-section">
<button class="detail-close" id="detail-close">Close</button>
<h2 id="detail-title"></h2>
<div class="detail-filter" id="detail-filter">
  <label><input type="checkbox" id="filter-j" checked><span style="color:#42A5F5;">CON0 (J)</span></label>
  <label><input type="checkbox" id="filter-k" checked><span style="color:#FF9800;">CON1 (K)</span></label>
</div>
<div style="overflow-x:auto;">
<table class="detail-table" id="detail-table"></table>
</div>
</div>

<script>
const LINKS = {links_json};
const OAM_MAP = {oam_map_json};
const OAM_SUMM = {oam_summary_json};
const STATS = {stats_json};
const N_OAMS = {num_oams_json};

const COL_J = '#42A5F5';
const COL_K = '#FF9800';
const SVG_SIZE = 780;
const CX = SVG_SIZE / 2;
const CY = SVG_SIZE / 2;
const R_NODE = 200;
const R_DRAW = 150;

(function(){{
  const sb = document.getElementById('stats-bar');
  const items = [
    {{l:'OAM Modules', v:N_OAMS, c:'#444'}},
    {{l:'AC Caps', v:STATS.total_caps, c:'#7E57C2'}},
    {{l:'Links', v:STATS.total_links, c:'#1565C0'}},
    {{l:'Unconnected', v:STATS.unconnected_pins, c:STATS.unconnected_pins>0?'#F44336':'#4CAF50'}},
  ];
  items.forEach(i=>{{const s=document.createElement('span');s.style.background=i.c;s.textContent=i.l+': '+i.v;sb.appendChild(s);}});
}})();

document.querySelectorAll('.tab-btn').forEach(btn=>{{
  btn.addEventListener('click', function(){{
    document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-'+btn.dataset.tab).classList.add('active');
  }});
}});

(function buildTopologyGraph(){{
  const svg = document.getElementById('topo-svg');
  const ns = 'http://www.w3.org/2000/svg';

  const nodePos = [];
  for(let i=1;i<=N_OAMS;i++){{
    const angle = -Math.PI/2 + 2*Math.PI*(i-1)/N_OAMS;
    nodePos[i] = {{
      x: CX + R_NODE * Math.cos(angle),
      y: CY + R_NODE * Math.sin(angle)
    }};
  }}

  const lineGroup = document.createElementNS(ns, 'g');
  svg.appendChild(lineGroup);

  const pairs = {{}};
  Object.values(OAM_SUMM).forEach(s=>{{
    const key = s.oam_a+'_'+s.oam_b;
    if(!pairs[key]) pairs[key] = {{a:s.oam_a, b:s.oam_b, sides:{{}}}};
    pairs[key].sides[s.side] = s;
  }});

  Object.values(pairs).forEach(p=>{{
    const a=p.a, b=p.b;
    const ax=nodePos[a].x, ay=nodePos[a].y;
    const bx=nodePos[b].x, by=nodePos[b].y;
    const dx=bx-ax, dy=by-ay;
    const len=Math.sqrt(dx*dx+dy*dy);
    const nx=-dy/len, ny=dx/len;

    const sides = Object.keys(p.sides);
    const offsetBase = sides.length === 2 ? 8 : 0;

    sides.forEach((side, si)=>{{
      const info = p.sides[side];
      const offset = sides.length === 2 ? (si === 0 ? -8 : 8) : 0;
      const color = side === 'JJ' ? COL_J : COL_K;

      const x1 = ax + nx*offset, y1 = ay + ny*offset;
      const x2 = bx + nx*offset, y2 = by + ny*offset;

      const mx = (x1+x2)/2 + nx*offset*0.5;
      const my = (y1+y2)/2 + ny*offset*0.5;

      const path = document.createElementNS(ns, 'path');
      path.setAttribute('d', 'M'+x1+','+y1+' Q'+mx+','+my+' '+x2+','+y2);
      path.setAttribute('stroke', color);
      path.setAttribute('class', 'conn-line');
      path.setAttribute('opacity', '0.7');
      path.style.strokeWidth = Math.max(2, Math.min(6, info.count / 10));
      path.dataset.oamA = a;
      path.dataset.oamB = b;
      path.dataset.side = side;
      path.dataset.count = info.count;

      path.addEventListener('mouseenter', function(e){{
        showLineTooltip(e, this);
      }});
      path.addEventListener('mouseleave', hideLineTooltip);
      path.addEventListener('click', function(){{
        showDetail(this.dataset.oamA, this.dataset.oamB, this.dataset.side);
      }});

      lineGroup.appendChild(path);

      const label = document.createElementNS(ns, 'text');
      label.setAttribute('x', mx);
      label.setAttribute('y', my - 6);
      label.setAttribute('class', 'conn-label');
      label.textContent = info.count + 'p';
      lineGroup.appendChild(label);
    }});
  }});

  for(let i=1;i<=N_OAMS;i++){{
    const g = document.createElementNS(ns, 'g');
    g.setAttribute('class', 'oam-node');
    g.dataset.oamIdx = i;

    const circle = document.createElementNS(ns, 'circle');
    circle.setAttribute('cx', nodePos[i].x);
    circle.setAttribute('cy', nodePos[i].y);
    circle.setAttribute('r', '28');
    circle.setAttribute('fill', '#2d2d44');
    circle.setAttribute('stroke', '#81C784');
    circle.setAttribute('stroke-width', '2');
    circle.setAttribute('class', 'oam-circle');
    g.appendChild(circle);

    const text = document.createElementNS(ns, 'text');
    text.setAttribute('x', nodePos[i].x);
    text.setAttribute('y', nodePos[i].y + 4);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('class', 'oam-label');
    text.textContent = 'OAM' + i;
    g.appendChild(text);

    const sub = document.createElementNS(ns, 'text');
    sub.setAttribute('x', nodePos[i].x);
    sub.setAttribute('y', nodePos[i].y + 38);
    sub.setAttribute('text-anchor', 'middle');
    sub.setAttribute('class', 'oam-sub');
    sub.textContent = 'J'+i+' / K'+i;
    g.appendChild(sub);

    g.addEventListener('click', function(){{
      showOamDetail(i);
    }});

    svg.appendChild(g);
  }}

  const tt = document.createElement('div');
  tt.id = 'line-tooltip';
  tt.style.cssText = 'display:none;position:fixed;background:#2d2d44;border:1px solid #555;padding:7px 10px;border-radius:4px;font-size:11px;z-index:100;pointer-events:none;box-shadow:0 4px 12px rgba(0,0,0,0.5);white-space:nowrap;';
  document.body.appendChild(tt);

  function showLineTooltip(e, el){{
    const s = el.dataset.side === 'JJ' ? 'CON0 (J-J)' : 'CON1 (K-K)';
    tt.innerHTML = '<b>OAM'+el.dataset.oamA+' ↔ OAM'+el.dataset.oamB+'</b><br>'+s+': '+el.dataset.count+' pins';
    tt.style.display = 'block';
    tt.style.left = (e.clientX+14)+'px';
    tt.style.top = (e.clientY+14)+'px';
  }}
  function hideLineTooltip(){{ tt.style.display='none'; }}
}})();

  function netSortKey(net){{
    const m = net.match(/^(.*[._])(P|N)_(\\d+)$/i);
    if(!m) return net;
    return m[1] + m[2].toUpperCase() + '_' + String(parseInt(m[3])).padStart(3,'0');
  }}

  function getConnPrefix(l){{ return l.oam_a.startsWith('J') ? 'J' : 'K'; }}

  function netNumMismatch(netA, netB){{
    const re = /_(\\d+)$/;
    const ma = netA.match(re), mb = netB.match(re);
    if(!ma || !mb) return false;
    return ma[1] !== mb[1];
  }}

  function showDetail(oamA, oamB, side){{
  const sec = document.getElementById('detail-section');
  const title = document.getElementById('detail-title');
  const tbl = document.getElementById('detail-table');
  const filterJ = document.getElementById('filter-j');
  const filterK = document.getElementById('filter-k');

  const lo = Math.min(parseInt(oamA), parseInt(oamB));
  const hi = Math.max(parseInt(oamA), parseInt(oamB));
  const loJ = 'J'+lo, loK = 'K'+lo;
  const hiJ = 'J'+hi, hiK = 'K'+hi;

  title.textContent = 'OAM'+lo+' ↔ OAM'+hi+' : Pin-to-Pin Links';
  filterJ.checked = side === 'JJ';
  filterK.checked = side === 'KK';

  function render(){{
    const showJ = filterJ.checked;
    const showK = filterK.checked;
    let filtered = LINKS.filter(l=>{{
      const isJ = l.oam_a.startsWith('J') && l.oam_b.startsWith('J');
      const isK = l.oam_a.startsWith('K') && l.oam_b.startsWith('K');
      if(isJ && !showJ) return false;
      if(isK && !showK) return false;
      const aSet = isJ ? loJ : loK;
      const bSet = isJ ? hiJ : hiK;
      const match1 = (l.oam_a===aSet && l.oam_b===bSet);
      const match2 = (l.oam_a===bSet && l.oam_b===aSet);
      return match1 || match2;
    }});

    filtered = filtered.map(l=>{{
      const isJ = l.oam_a.startsWith('J');
      const aSet = isJ ? loJ : loK;
      if(l.oam_a === aSet) return l;
      return {{
        oam_a: l.oam_b, pinname_a: l.pinname_b, pinnumber_a: l.pinnumber_b, net_a: l.net_b,
        cap_refdes: l.cap_refdes, cap_partvalue: l.cap_partvalue,
        net_b: l.net_a, pinnumber_b: l.pinnumber_a, pinname_b: l.pinname_a, oam_b: l.oam_a
      }};
    }});

    filtered.sort((a,b)=>{{
      const ka = netSortKey(a.net_a);
      const kb = netSortKey(b.net_a);
      return ka < kb ? -1 : ka > kb ? 1 : 0;
    }});

    const loRef = showJ && !showK ? loJ : !showJ && showK ? loK : loJ;
    const hiRef = showJ && !showK ? hiJ : !showJ && showK ? hiK : hiJ;
    let html = '<thead><tr><th>'+loRef+'</th><th>Pin#</th><th>PinName</th><th>Net_A</th><th>AC Cap</th><th>Net_B</th><th>PinName</th><th>Pin#</th><th>'+hiRef+'</th></tr></thead><tbody>';
    if(filtered.length===0){{
      html += '<tr><td colspan="9" style="text-align:center;color:#888;">No links</td></tr>';
    }}
    filtered.forEach(l=>{{
      const mm = netNumMismatch(l.net_a, l.net_b);
      const rowStyle = mm ? ' style="background:#4a2020;"' : '';
      html += '<tr'+rowStyle+'>';
      html += '<td>'+l.oam_a+'</td>';
      html += '<td style="color:#aaa;">'+l.pinnumber_a+'</td>';
      html += '<td>'+l.pinname_a+'</td>';
      html += '<td style="color:#81C784;">'+l.net_a+'</td>';
      html += '<td style="color:#FFB74D;">'+l.cap_refdes+'</td>';
      html += '<td style="color:'+(mm?'#F44336':'#81C784')+';">'+l.net_b+'</td>';
      html += '<td>'+l.pinname_b+'</td>';
      html += '<td style="color:#aaa;">'+l.pinnumber_b+'</td>';
      html += '<td>'+l.oam_b+'</td>';
      html += '</tr>';
    }});
    html += '</tbody>';
    tbl.innerHTML = html;
  }}

  render();
  filterJ.onchange = render;
  filterK.onchange = render;

  sec.style.display = 'block';
  sec.scrollIntoView({{behavior:'smooth'}});
}}

function showOamDetail(idx){{
  const sec = document.getElementById('detail-section');
  const title = document.getElementById('detail-title');
  const tbl = document.getElementById('detail-table');
  const filterJ = document.getElementById('filter-j');
  const filterK = document.getElementById('filter-k');

  const jRef = 'J'+idx;
  const kRef = 'K'+idx;
  title.textContent = 'OAM'+idx+' ('+jRef+'/'+kRef+') : All Connections';

  filterJ.checked = true;
  filterK.checked = true;

  function render(){{
    const showJ = filterJ.checked;
    const showK = filterK.checked;
    let filtered = LINKS.filter(l=>{{
      const isJ = l.oam_a.startsWith('J') && l.oam_b.startsWith('J');
      const isK = l.oam_a.startsWith('K') && l.oam_b.startsWith('K');
      if(isJ && !showJ) return false;
      if(isK && !showK) return false;
      const mine = l.oam_a===jRef||l.oam_a===kRef||l.oam_b===jRef||l.oam_b===kRef;
      if(!mine) return false;
      return true;
    }});

    filtered = filtered.map(l=>{{
      const isJ = l.oam_a.startsWith('J');
      const myRef = isJ ? jRef : kRef;
      if(l.oam_a === myRef) return l;
      return {{
        oam_a: l.oam_b, pinname_a: l.pinname_b, pinnumber_a: l.pinnumber_b, net_a: l.net_b,
        cap_refdes: l.cap_refdes, cap_partvalue: l.cap_partvalue,
        net_b: l.net_a, pinnumber_b: l.pinnumber_a, pinname_b: l.pinname_a, oam_b: l.oam_a
      }};
    }});

    filtered.sort((a,b)=>{{
      const isJ = a.oam_a.startsWith('J');
      const aGroup = isJ ? '0' : '1';
      const bGroup = b.oam_a.startsWith('J') ? '0' : '1';
      if(aGroup !== bGroup) return aGroup < bGroup ? -1 : 1;
      const ka = netSortKey(a.net_a);
      const kb = netSortKey(b.net_a);
      return ka < kb ? -1 : ka > kb ? 1 : 0;
    }});

    let html = '<thead><tr><th>'+jRef+'/'+kRef+'</th><th>Pin#</th><th>PinName</th><th>Net_A</th><th>AC Cap</th><th>Net_B</th><th>PinName</th><th>Pin#</th><th>Partner</th></tr></thead><tbody>';
    if(filtered.length===0){{
      html += '<tr><td colspan="9" style="text-align:center;color:#888;">No links</td></tr>';
    }}
    filtered.forEach(l=>{{
      const mm = netNumMismatch(l.net_a, l.net_b);
      const rowStyle = mm ? ' style="background:#4a2020;"' : '';
      html += '<tr'+rowStyle+'>';
      html += '<td>'+l.oam_a+'</td>';
      html += '<td style="color:#aaa;">'+l.pinnumber_a+'</td>';
      html += '<td>'+l.pinname_a+'</td>';
      html += '<td style="color:#81C784;">'+l.net_a+'</td>';
      html += '<td style="color:#FFB74D;">'+l.cap_refdes+'</td>';
      html += '<td style="color:'+(mm?'#F44336':'#81C784')+';">'+l.net_b+'</td>';
      html += '<td>'+l.pinname_b+'</td>';
      html += '<td style="color:#aaa;">'+l.pinnumber_b+'</td>';
      html += '<td>'+l.oam_b+'</td>';
      html += '</tr>';
    }});
    html += '</tbody>';
    tbl.innerHTML = html;
  }}

  render();
  filterJ.onchange = render;
  filterK.onchange = render;

  sec.style.display = 'block';
  sec.scrollIntoView({{behavior:'smooth'}});
}}

document.getElementById('detail-close').addEventListener('click', function(){{
  document.getElementById('detail-section').style.display = 'none';
}});

(function buildMatrix(){{
  const tbl = document.getElementById('matrix-table');
  const oamLinks = {{}};
  Object.values(OAM_SUMM).forEach(s=>{{
    const key = s.oam_a+'_'+s.oam_b;
    if(!oamLinks[key]) oamLinks[key] = {{j:0,k:0}};
    if(s.side==='JJ') oamLinks[key].j = s.count;
    if(s.side==='KK') oamLinks[key].k = s.count;
  }});

  let hdr = '<thead><tr><th></th>';
  for(let i=1;i<=N_OAMS;i++) hdr += '<th>OAM'+i+'</th>';
  hdr += '</tr></thead><tbody>';
  for(let i=1;i<=N_OAMS;i++){{
    hdr += '<tr><th>OAM'+i+'</th>';
    for(let j=1;j<=N_OAMS;j++){{
      if(i===j){{ hdr += '<td class="self">-</td>'; continue; }}
      const key = Math.min(i,j)+'_'+Math.max(i,j);
      const info = oamLinks[key] || {{j:0,k:0}};
      if(info.j===0 && info.k===0){{
        hdr += '<td class="zero">0</td>';
      }} else {{
        let txt = '';
        let cls = '';
        if(info.j>0) {{ txt += '<span style="color:#42A5F5;">'+info.j+'</span>'; }}
        if(info.j>0 && info.k>0) txt += '/';
        if(info.k>0) {{ txt += '<span style="color:#FF9800;">'+info.k+'</span>'; }}
        hdr += '<td class="val-mix" style="cursor:pointer;" data-a="'+Math.min(i,j)+'" data-b="'+Math.max(i,j)+'">'+txt+'</td>';
      }}
    }}
    hdr += '</tr>';
  }}
  hdr += '</tbody>';
  tbl.innerHTML = hdr;

  tbl.addEventListener('click', function(e){{
    const td = e.target.closest('td[data-a]');
    if(!td) return;
    showDetail(td.dataset.a, td.dataset.b, 'JJ');
  }});
}})();
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    args = parse_args()

    if not os.path.isfile(args.pin_nets_csv):
        print(f"ERROR: File not found: {args.pin_nets_csv}")
        sys.exit(1)

    csv_dir = os.path.dirname(os.path.abspath(args.pin_nets_csv))
    output_dir = args.output_dir or csv_dir
    os.makedirs(output_dir, exist_ok=True)

    connector_set = set(args.connectors)
    connector_list = args.connectors

    print("=" * 50)
    print("  UBB OAM Topology Discovery Tool")
    print("=" * 50)
    print(f"  CSV: {args.pin_nets_csv}")
    print(f"  Connectors: {', '.join(connector_list)}")
    print(f"  Output: {output_dir}")
    print()

    print("Reading CSV ...")
    rows = read_csv(args.pin_nets_csv)
    print(f"  Total rows: {len(rows)}")

    print("Building indexes ...")
    net_map, comp_map = build_indexes(rows)
    print(f"  Unique nets: {len(net_map)}")
    print(f"  Unique components: {len(comp_map)}")

    print("Filtering OAM connector pins ...")
    oam_pins = find_oam_pins(rows, connector_set)
    print(f"  OAM connector pins: {len(oam_pins)}")

    skip_nets = set(args.skip_nets)
    oam_nets = get_oam_nets(oam_pins, skip_nets)
    print(f"  OAM signal nets (excl power/ground): {len(oam_nets)}")

    print("Finding AC coupling capacitors ...")
    caps = find_bridging_caps(net_map, comp_map, oam_nets, connector_set)
    print(f"  Bridging capacitors found: {len(caps)}")

    print("Tracing topology ...")
    links = trace_topology(caps, net_map, connector_set)
    print(f"  Total pin-to-pin links: {len(links)}")

    print("Building connection matrix ...")
    matrix = build_matrix(links, connector_list)

    detail_path = os.path.join(output_dir, "topology_detail.csv")
    pair_path = os.path.join(output_dir, "topology_pair_detail.csv")
    html_path = os.path.join(output_dir, "topology_report.html")

    oam_map, _ = build_oam_map(connector_list)

    print(f"Writing {os.path.basename(detail_path)} ...")
    write_detail_csv(links, detail_path)

    print(f"Writing {os.path.basename(pair_path)} ...")
    write_pair_detail_csv(links, oam_map, pair_path)

    stats = {
        "total_connectors": len(connector_list),
        "total_caps": len(caps),
        "total_links": len(links),
    }

    print(f"Generating {os.path.basename(html_path)} ...")
    generate_html(links, matrix, connector_list, html_path, stats)

    print()
    print("=" * 50)
    print("  SUMMARY")
    print("=" * 50)
    print(f"  Connectors:         {stats['total_connectors']}")
    print(f"  AC coupling caps:   {stats['total_caps']}")
    print(f"  Pin-to-pin links:   {stats['total_links']}")
    print()
    print("  Output files:")
    print(f"    {html_path}")
    print(f"    {pair_path}")
    print(f"    {detail_path}")
    print()
    print("Done. Open HTML file in browser to view interactive report.")


if __name__ == "__main__":
    main()
