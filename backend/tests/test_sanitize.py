from app.sanitize import sanitize_svg

BASE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">{}</svg>'


def test_keeps_drawing_elements():
    out = sanitize_svg(BASE.format('<rect width="5" height="5" fill="#000"/>'))
    assert "<rect" in out and 'fill="#000"' in out
    assert 'xmlns="http://www.w3.org/2000/svg"' in out


def test_strips_script():
    assert "<script" not in sanitize_svg(BASE.format("<script>x()</script>"))


def test_strips_foreign_object():
    out = sanitize_svg(BASE.format(
        '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">x</div>'
        "</foreignObject>"))
    assert "foreignObject" not in out


def test_strips_event_handlers():
    out = sanitize_svg(BASE.format('<rect width="1" height="1" onload="x()"/>'))
    assert "onload" not in out


def test_strips_external_href():
    out = sanitize_svg(BASE.format('<rect href="http://evil" width="1" height="1"/>'))
    assert "href" not in out


def test_rejects_non_svg():
    assert sanitize_svg("<div>hi</div>") == ""
    assert sanitize_svg("not xml") == ""
    assert sanitize_svg("") == ""
