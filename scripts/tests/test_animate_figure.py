"""Tests for animate_figure.py — SVG の data-step を、順に現れるコマと GIF にする道具。

守るのは三つ。現れる前の要素がコマに無いこと、line が始点から伸びること、GIF が最後のコマで止まること
（最後の遅延が落ちると、読者が読み終える前に図が消えて頭から繰り返す）。
"""

from __future__ import annotations

import shutil
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import animate_figure as af

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
<rect width="200" height="200" fill="#FAFAF7"/>
<text x="10" y="30" font-size="20">title</text>
<rect data-step="1" x="20" y="60" width="60" height="40" fill="none" stroke="#242321" stroke-width="5"/>
<line data-step="2" x1="80" y1="80" x2="180" y2="80" stroke="#242321" stroke-width="5"/>
{extra}
</svg>"""

needs_tools = pytest.mark.skipif(
    not (shutil.which("rsvg-convert") and shutil.which("ffmpeg")), reason="rsvg-convert と ffmpeg が要る"
)


def tags(tree: ET.Element) -> list[str]:
    return [el.tag.split("}")[-1] for el in tree]


def test_elements_are_absent_before_their_step() -> None:
    root = ET.fromstring(SVG.format(extra=""))
    tree, key = af.frame_tree(root, 0.0)
    assert tags(tree) == ["rect", "text"]
    assert key == (0.0, 0.0)


def test_all_elements_are_present_after_the_last_step() -> None:
    root = ET.fromstring(SVG.format(extra=""))
    tree, key = af.frame_tree(root, af.LEAD + af.INTERVAL + af.FADE)
    assert tags(tree) == ["rect", "text", "rect", "line"]
    assert key == (1.0, 1.0)
    assert all(el.get("data-step") is None for el in tree)


def test_line_grows_from_its_start_point() -> None:
    root = ET.fromstring(SVG.format(extra=""))
    tree, _ = af.frame_tree(root, af.LEAD + af.INTERVAL + af.FADE / 4)
    line = [el for el in tree if el.tag.endswith("line")][0]
    assert line.get("x1") == "80"
    assert 80 < float(line.get("x2")) < 180


def test_double_headed_line_grows_from_the_middle() -> None:
    el = ET.fromstring('<line x1="0" y1="0" x2="100" y2="0" marker-start="url(#a)" marker-end="url(#a)"/>')
    af.grow_line(el, 0.5)
    assert (float(el.get("x1")), float(el.get("x2"))) == (25.0, 75.0)


def test_fading_element_keeps_its_own_opacity_and_transform() -> None:
    root = ET.fromstring(
        SVG.format(extra='<text data-step="3" x="10" y="150" opacity="0.5" transform="rotate(5)">a</text>')
    )
    tree, _ = af.frame_tree(root, af.LEAD + 2 * af.INTERVAL + af.FADE / 4)
    text = [el for el in tree if el.get("transform")][0]
    assert 0 < float(text.get("opacity")) < 0.5
    assert text.get("transform").startswith("translate(0 ") and text.get("transform").endswith("rotate(5)")


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ('<text data-step="x">a</text>', "整数"),
        ('<text><tspan data-step="3">a</tspan></text>', "tspan"),
        ('<text data-step="4">a</text>', "連番"),
    ],
)
def test_bad_step_numbers_are_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str], extra: str, message: str) -> None:
    svg = tmp_path / "f.svg"
    svg.write_text(SVG.format(extra=extra), encoding="utf-8")
    assert af.main([str(svg), str(tmp_path / "f.mp4")]) == 1
    assert message in capsys.readouterr().err


def test_svg_without_steps_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    svg = tmp_path / "f.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"/>', encoding="utf-8")
    assert af.main([str(svg), str(tmp_path / "f.mp4")]) == 1
    assert "data-step" in capsys.readouterr().err


def test_odd_size_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    svg = tmp_path / "f.svg"
    svg.write_text(SVG.format(extra=""), encoding="utf-8")
    assert af.main([str(svg), str(tmp_path / "f.mp4"), "--size", "201"]) == 1
    assert "奇数" in capsys.readouterr().err


@needs_tools
def test_gif_holds_on_the_last_frame(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    svg = tmp_path / "f.svg"
    svg.write_text(SVG.format(extra=""), encoding="utf-8")
    gif, sheet = tmp_path / "f.gif", tmp_path / "f.sheet.png"
    assert af.main([str(svg), str(tmp_path / "f.mp4"), "--sheet", str(sheet), "--gif", str(gif)]) == 0
    assert "2 段" in capsys.readouterr().out
    assert sheet.stat().st_size > 0
    data = gif.read_bytes()
    delays, i = [], data.find(b"\x21\xf9\x04")
    while i >= 0:
        delays.append(struct.unpack("<H", data[i + 4 : i + 6])[0])
        i = data.find(b"\x21\xf9\x04", i + 8)
    assert delays[-1] == round(af.GIF_HOLD * 100)
    assert len(delays) < 40  # 同じ絵のコマをまとめている（まとめないと 80 コマを超える）
