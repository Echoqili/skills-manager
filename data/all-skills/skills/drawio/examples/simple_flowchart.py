#!/usr/bin/env python3
"""
draw.io Simple Flowchart Generator
====================================
Generates a .drawio file for a simple login flowchart,
then optionally exports to PNG/SVG/PDF using the draw.io CLI.

Usage:
    python simple_flowchart.py                         # generates login-flow.drawio
    python simple_flowchart.py --export png            # generates login-flow.drawio.png
    python simple_flowchart.py --export svg --open     # exports SVG and opens the file
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# 1. Define the flowchart data
# ---------------------------------------------------------------------------

FLOWCHART_TITLE = "Login Flowchart"

# Each node: (id, label, x, y, width, height, style)
NODES = [
    ("n1", "Start",            40,  40,  120, 60, "rounded;fillColor=#dae8fc;strokeColor=#6c8ebf;"),
    ("n2", "Enter Credentials", 40, 140, 120, 60, "fillColor=#fff2cc;strokeColor=#d6b656;"),
    ("n3", "Validate",         40, 240, 120, 60, "fillColor=#fff2cc;strokeColor=#d6b656;"),
    ("n4", "Access Granted",   40, 380, 120, 60, "rounded;fillColor=#d5e8d4;strokeColor=#82b366;"),
    ("n5", "Access Denied",   220, 380, 120, 60, "rounded;fillColor=#f8cecc;strokeColor=#b85450;"),
]

# Each edge: (id, source, target, label)
EDGES = [
    ("e1", "n1", "n2", ""),
    ("e2", "n2", "n3", ""),
    ("e3", "n3", "n4", "Valid"),
    ("e4", "n3", "n5", "Invalid"),
]


# ---------------------------------------------------------------------------
# 2. Generate draw.io XML
# ---------------------------------------------------------------------------

def build_drawio_xml(title, nodes, edges):
    mxgraph = ET.Element("mxGraphModel", attrib={
        "dx": "800",
        "dy": "600",
        "grid": "1",
        "gridSize": "10",
        "guides": "1",
        "tooltips": "1",
        "connect": "1",
        "arrows": "1",
        "fold": "1",
        "page": "1",
        "pageScale": "1",
        "pageWidth": "827",
        "pageHeight": "1169",
        "math": "0",
        "shadow": "0",
    })
    root = ET.SubElement(mxgraph, "root")

    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    for nid, label, x, y, w, h, style in nodes:
        geo = ET.Element("mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), as_="geometry")
        cell = ET.Element("mxCell", id=nid, value=label, style=style, vertex="1", parent="1")
        cell.append(geo)
        root.append(cell)

    for eid, src, tgt, label in edges:
        geo = ET.Element("mxGeometry", relative="1", as_="geometry")
        cell = ET.Element("mxCell", id=eid, value=label, style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;", edge="1", parent="1", source=src, target=tgt)
        cell.append(geo)
        root.append(cell)

    return ET.tostring(mxgraph, encoding="unicode", xml_declaration=False)


def write_drawio_file(xml_str, output_path):
    content = (
        '<mxfile host="app.diagrams.net" agent="Python drawio Skill" version="24.2.5">\n'
        f"  <diagram name=\"{FLOWCHART_TITLE}\" id=\"diagram-1\">\n"
        f"    {xml_str}\n"
        f"  </diagram>\n"
        f"</mxfile>\n"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


# ---------------------------------------------------------------------------
# 3. draw.io CLI helpers
# ---------------------------------------------------------------------------

def find_drawio_cli():
    cmd = shutil.which("drawio") or shutil.which("draw.io")
    if cmd:
        return cmd

    system = platform.system()
    if system == "Darwin":
        path = "/Applications/draw.io.app/Contents/MacOS/draw.io"
    elif system == "Windows":
        path = r"C:\Program Files\draw.io\draw.io.exe"
    else:
        path = None

    if path and os.path.exists(path):
        return path
    return None


def export_diagram(drawio_path, fmt, cli_path):
    output = f"{drawio_path}.{fmt}"
    cmd = [
        cli_path, "-x",
        "-f", fmt,
        "-e",
        "-b", "10",
        "-o", output,
        drawio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Export failed: {result.stderr.strip()}", file=sys.stderr)
        return None
    return output


def open_file(filepath):
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", filepath])
        elif system == "Windows":
            os.startfile(filepath)
        else:
            subprocess.run(["xdg-open", filepath])
    except Exception as e:
        print(f"Could not open file: {e}", file=sys.stderr)
        print(f"  File saved at: {os.path.abspath(filepath)}")


# ---------------------------------------------------------------------------
# 4. Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a draw.io login flowchart")
    parser.add_argument("--export", choices=["png", "svg", "pdf"], help="Export to format using draw.io CLI")
    parser.add_argument("--open", action="store_true", help="Open the generated file after creation")
    args = parser.parse_args()

    base_name = "login-flow"
    drawio_file = f"{base_name}.drawio"

    xml_str = build_drawio_xml(FLOWCHART_TITLE, NODES, EDGES)
    write_drawio_file(xml_str, drawio_file)
    print(f"Created: {os.path.abspath(drawio_file)}")

    if args.export:
        cli = find_drawio_cli()
        if cli is None:
            print("draw.io CLI not found. Install the draw.io desktop app to enable export.")
            print(f"The .drawio file is ready at: {os.path.abspath(drawio_file)}")
            sys.exit(1)

        exported = export_diagram(drawio_file, args.export, cli)
        if exported:
            os.remove(drawio_file)
            print(f"Exported: {os.path.abspath(exported)}")
            if args.open:
                open_file(exported)
    elif args.open:
        open_file(drawio_file)


if __name__ == "__main__":
    main()