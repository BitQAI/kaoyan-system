"""内联 SVG 白名单净化。

metadata 里的 svg 是自家链路产物，但仍是字符串注入面：只放行绘图标签与属性，
script / foreignObject / 事件属性 / 外链一律丢弃。服务端出口净化，前端拿到的就是干净的。
"""
import re
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"

ALLOWED_TAGS = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline",
    "polygon", "text", "tspan", "defs", "clipPath", "marker", "title", "desc",
    "linearGradient", "radialGradient", "stop",
}

#: 整棵子树丢弃，不只是去标签
DROPPED_TAGS = {"script", "foreignObject", "iframe", "image", "use", "style"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _attr_ok(name: str, value: str) -> bool:
    local = _local(name).lower()
    if local.startswith("on"):
        return False
    if local in {"href", "src", "formaction"} or "href" in local:
        return False
    if local == "style":
        low = value.lower()
        return "url(" not in low and "expression(" not in low
    return True


def _clean(el: ET.Element) -> None:
    for child in list(el):
        tag = _local(child.tag)
        if tag in DROPPED_TAGS or not tag[:1].isalpha():
            el.remove(child)
            continue
        _clean(child)
    kept = {_local(k): v for k, v in el.attrib.items() if _attr_ok(k, v)}
    el.attrib.clear()
    el.attrib.update(kept)


def sanitize_svg(svg: str) -> str:
    """返回净化后的 SVG 字符串；无法解析或根节点不是 svg 时返回空串。"""
    if not svg or "<svg" not in svg:
        return ""
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return ""
    if _local(root.tag) != "svg":
        return ""
    _clean(root)
    for el in root.iter():
        el.tag = _local(el.tag)
    out = ET.tostring(root, encoding="unicode")
    if "xmlns=" not in out.split(">", 1)[0]:
        out = out.replace("<svg", f'<svg xmlns="{SVG_NS}"', 1)
    return re.sub(r"<(/?)(?:ns\d+:)", r"<\1", out)
