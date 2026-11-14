#!/usr/bin/env python3
"""1枚の図の SVG を、要素が順に現れる MP4 と GIF にする。

SVG の要素に data-step="1" のように、現れる順の番号を付けておく。番号は1からの連番にする。
番号の無い要素は最初から出ている。同じ番号の要素は一緒に現れる。line は始点から終点へ伸び、
両端に矢じりのある line は中央から両側へ伸びる。ほかの要素（g でまとめたものも）は、少し下から
上がりながら濃くなる。番号は SVG を PNG に変換する道具には無視されるので、止まった図は同じ SVG から
今までどおり作れる。

描く道具は、rsvg-convert があればそれを使い、無ければ cairosvg を使う（cairosvg は font-weight の
500 を普通の太さで描く）。動画にまとめる道具は ffmpeg で、無ければ imageio-ffmpeg に入っているものを使う。

使い方（repo の根で）
    uv run --project scripts python scripts/animate_figure.py figures/SLUG-WHAT.svg OUT/SLUG-WHAT.mp4 \
        --sheet OUT/SLUG-WHAT.sheet.png --gif images/SLUG-WHAT.gif

--sheet を付けると、番号ごとに現れきったコマを1枚に並べた PNG も書き出す。動画を見る代わりに、
この1枚を開いて、順番、はみ出し、文字の化けを確かめる。

--gif を付けると、記事の本文に置く GIF も書き出す。一辺 900px、15fps、同じ絵が続くコマは1枚にまとめ、
全部出たコマで GIF_HOLD 秒止まってから繰り返す。コマをまとめるのは、止まっている時間をコマ数で持つと
1枚の図が 250 コマ近くになり、読み込む側の負担になるため。

最後の行に、段の数、長さ、Buffer に渡すサムネイルの位置（ミリ秒）を出す。

著者が通勤学習の講義の図を投稿用の動画にするのに使っている道具に、エッセイの図のための --gif を足した版。
描き方の約束（data-step）は同じ。図の決まりは .claude/skills/writing-ecosystem/references/essay-figures.md が持つ。
"""
import argparse
import copy
import math
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

FPS = 30
LEAD = 0.8      # 題だけを見せる時間（秒）
INTERVAL = 1.0  # 次の番号が現れ始めるまでの間隔
FADE = 0.5      # 一つの番号が現れきるまでの時間
HOLD = 3.5      # 全部出たあと止めておく時間
RISE = 14       # 現れるときに上がる距離（px）
GIF_SIZE = 900  # GIF の一辺（px）
GIF_FPS = 15
GIF_HOLD = 8.0  # GIF で、全部出たあと止めておく時間（秒）


def ease(p: float) -> float:
    """はじめ速く、終わりにゆっくり。"""
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def frame_tree(root: ET.Element, t: float) -> tuple[ET.Element, tuple]:
    """時刻 t のコマの SVG と、同じ絵かどうかを見分ける鍵を返す。"""
    out = copy.deepcopy(root)
    key = []
    for parent in list(out.iter()):
        for el in list(parent):
            step = el.attrib.pop("data-step", None)
            if step is None:
                continue
            e = round(ease((t - (LEAD + (int(step) - 1) * INTERVAL)) / FADE), 3)
            key.append(e)
            if e <= 0:
                parent.remove(el)
            elif e < 1:
                if el.tag.split("}")[-1] == "line":
                    grow_line(el, max(e, 0.06))
                else:
                    # もとの opacity と transform は残す。上がる動きは図の座標で行うので、前に置く
                    el.set("opacity", f"{e * float(el.get('opacity', '1')):.3f}")
                    shift = f"translate(0 {(1 - e) * RISE:.2f})"
                    el.set("transform", (shift + " " + el.get("transform", "")).strip())
    return out, tuple(key)


def grow_line(el: ET.Element, g: float) -> None:
    x1, y1, x2, y2 = (float(el.get(k, "0")) for k in ("x1", "y1", "x2", "y2"))
    if el.get("marker-start") and el.get("marker-end"):
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        el.set("x1", f"{cx + (x1 - cx) * g:.2f}")
        el.set("y1", f"{cy + (y1 - cy) * g:.2f}")
        el.set("x2", f"{cx + (x2 - cx) * g:.2f}")
        el.set("y2", f"{cy + (y2 - cy) * g:.2f}")
    else:
        el.set("x2", f"{x1 + (x2 - x1) * g:.2f}")
        el.set("y2", f"{y1 + (y2 - y1) * g:.2f}")


def make_renderer(size: int, tmp: Path):
    """SVG の bytes を PNG の bytes にする関数と、道具の名前を返す。"""
    rsvg = shutil.which("rsvg-convert")
    if rsvg:
        src, dst = tmp / "frame.svg", tmp / "frame.png"

        def render(svg: bytes) -> bytes:
            src.write_bytes(svg)
            subprocess.run([rsvg, "-w", str(size), "-h", str(size), "-o", str(dst), str(src)], check=True)
            return dst.read_bytes()

        return render, "rsvg-convert"
    try:
        import cairosvg
    except ImportError:
        return None, ""
    return (lambda svg: cairosvg.svg2png(bytestring=svg, output_width=size, output_height=size)), "cairosvg"


def find_ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
    except ImportError:
        return None
    return imageio_ffmpeg.get_ffmpeg_exe()


def write_gif(ffmpeg: str, mp4: str, gif: str) -> None:
    """MP4 から GIF を作る。同じ絵が続くコマは mpdecimate で落とし、表示時間は GIF のコマの遅延で持つ。"""
    vf = (f"fps={GIF_FPS},mpdecimate,scale={GIF_SIZE}:{GIF_SIZE}:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle")
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", mp4, "-vf", vf,
         "-final_delay", str(round(GIF_HOLD * 100)), "-loop", "0", gif],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("svg")
    ap.add_argument("mp4")
    ap.add_argument("--sheet", help="番号ごとに現れきったコマを並べた PNG の書き出し先")
    ap.add_argument("--size", type=int, default=None, help="動画の一辺の px。省くと SVG の width")
    ap.add_argument("--gif", help="記事の本文に置く GIF の書き出し先")
    args = ap.parse_args(argv)

    root = ET.fromstring(Path(args.svg).read_text(encoding="utf-8"))
    tagged = [el for el in root.iter() if el.get("data-step") is not None]
    if not tagged:
        print("data-step の付いた要素がありません。現れる順の番号を付けてください", file=sys.stderr)
        return 1
    bad = sorted({el.get("data-step", "") for el in tagged if not el.get("data-step", "").isdigit()})
    if bad:
        print(f"data-step は整数で書いてください: {bad}", file=sys.stderr)
        return 1
    if any(el.tag.split("}")[-1] == "tspan" for el in tagged):
        print("tspan に data-step が付いています。番号は text の側に付けてください（tspan は消えると後ろの文字が詰まる）", file=sys.stderr)
        return 1
    steps = sorted({int(el.get("data-step", "0")) for el in tagged})
    if steps != list(range(1, len(steps) + 1)):
        print(f"data-step が1からの連番になっていません: {steps}", file=sys.stderr)
        return 1
    width = re.match(r"[\d.]+", root.get("width", ""))
    size = args.size or (int(float(width.group())) if width else 1200)
    if size % 2:
        print(f"一辺が奇数です（{size}）。偶数にしてください", file=sys.stderr)
        return 1
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("ffmpeg がありません。apt-get install -y ffmpeg か pip install imageio-ffmpeg で入れてください"
              "（pip が externally-managed で拒んだら --break-system-packages を付ける）", file=sys.stderr)
        return 2

    total = LEAD + (len(steps) - 1) * INTERVAL + FADE + HOLD
    n = round(total * FPS)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        render, tool = make_renderer(size, tmp)
        if render is None:
            print("SVG を描く道具がありません。rsvg-convert（librsvg2-bin）か cairosvg を入れてください", file=sys.stderr)
            return 2
        drawn: dict[tuple, bytes] = {}
        for i in range(n):
            tree, key = frame_tree(root, i / FPS)
            if key not in drawn:
                drawn[key] = render(ET.tostring(tree, encoding="utf-8"))
            (tmp / f"f{i:05d}.png").write_bytes(drawn[key])
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(tmp / "f%05d.png"),
             "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", args.mp4],
            check=True,
        )
        if args.sheet:
            # 番号 k が現れきった時点のコマを順に並べる。最後の1枚は全部出た図
            picks = [round((LEAD + (k - 1) * INTERVAL + FADE) * FPS) + 1 for k in steps]
            for j, i in enumerate(picks):
                shutil.copy(tmp / f"f{min(i, n - 1):05d}.png", tmp / f"s{j:03d}.png")
            cols = min(3, len(picks))
            rows = math.ceil(len(picks) / cols)
            subprocess.run(
                [ffmpeg, "-y", "-loglevel", "error", "-i", str(tmp / "s%03d.png"),
                 "-vf", f"scale=600:600,tile={cols}x{rows}:padding=6:margin=6:color=0x888888",
                 "-frames:v", "1", args.sheet],
                check=True,
            )
    if args.gif:
        write_gif(ffmpeg, args.mp4, args.gif)
    print(f"{args.mp4}: {len(steps)} 段, {total:.1f} 秒, 描いた道具 {tool}, サムネイルの位置 {round((total - 0.5) * 1000)} ミリ秒")
    return 0


if __name__ == "__main__":
    sys.exit(main())
