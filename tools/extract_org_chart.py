"""Extract a coordinate-aware org-chart model from a PowerPoint deck.

The deck is treated as the source database: shape text is attached to its
slide coordinates, while connector endpoints are preferred when PowerPoint
has authored them. Missing connector endpoints fall back to nearest-shape
proximity, never to XML/text order.
"""

import argparse
import json
import math
import zipfile
from pathlib import Path
from xml.etree import ElementTree

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


def _number(node, attribute):
    return int(node.attrib.get(attribute, 0)) if node is not None else 0


def _box(shape):
    offset = shape.find(".//a:xfrm/a:off", NS)
    extent = shape.find(".//a:xfrm/a:ext", NS)
    x, y = _number(offset, "x"), _number(offset, "y")
    width, height = _number(extent, "cx"), _number(extent, "cy")
    return {"x": x, "y": y, "width": width, "height": height,
            "center_x": x + width / 2, "center_y": y + height / 2}


def _text(shape):
    return " ".join((node.text or "").strip() for node in shape.findall(".//a:t", NS)).strip()


def _distance(a, b):
    b = b.get("box", b)
    return math.hypot(a["center_x"] - b["center_x"], a["center_y"] - b["center_y"])


def extract_slide(xml_bytes, slide_number):
    root = ElementTree.fromstring(xml_bytes)
    nodes = {}
    for shape in root.findall(".//p:sp", NS):
        text = _text(shape)
        if not text:
            continue
        properties = shape.find("p:nvSpPr/p:cNvPr", NS)
        if properties is None:
            continue
        shape_id = properties.attrib["id"]
        nodes[shape_id] = {"id": shape_id, "text": text, "box": _box(shape)}

    edges = []
    for connector in root.findall(".//p:cxnSp", NS):
        properties = connector.find("p:nvCxnSpPr/p:cNvPr", NS)
        if properties is None:
            continue
        start = connector.find(".//a:stCxn", NS)
        end = connector.find(".//a:endCxn", NS)
        start_id = start.attrib.get("id") if start is not None else None
        end_id = end.attrib.get("id") if end is not None else None
        connected = [node_id for node_id in (start_id, end_id) if node_id in nodes]
        if len(connected) < 2:
            box = _box(connector)
            nearby = sorted(nodes, key=lambda node_id: _distance(box, nodes[node_id]))
            connected = nearby[:2]
        if len(connected) == 2 and connected[0] != connected[1]:
            edges.append({"from": connected[0], "to": connected[1], "source": "connector" if start_id and end_id else "proximity"})

    return {"slide": slide_number, "nodes": list(nodes.values()), "edges": edges}


def extract_deck(deck_path):
    slides = []
    with zipfile.ZipFile(deck_path) as archive:
        slide_paths = sorted(
            (name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")),
            key=lambda name: int(Path(name).stem.replace("slide", "")),
        )
        for slide_path in slide_paths:
            number = int(Path(slide_path).stem.replace("slide", ""))
            slides.append(extract_slide(archive.read(slide_path), number))
    return {"source": str(deck_path), "slides": slides}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pptx", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(extract_deck(args.pptx), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()