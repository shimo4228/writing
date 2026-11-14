# エッセイの動く図

note / Substack のエッセイと、研究リポジトリの論考に入れる図の決まりと手順。1 枚の図が、説明の順に一段ずつ
組み上がる GIF になる。読者は本文を読みながら、仕組みが現れる順を見る。SVG を手で書き、`scripts/animate_figure.py` で
GIF にする。Zenn の技術記事の図（静止画の PNG）は `zenn-format` の Figures と skill: `mono-figure` が持ち、色と寸法の決まりは別。

## いつ、何を図にするか

- 作るのは内容 GO の後（`writing-ecosystem` §4）。brief の Figure plan に、節 → 形（対比 / 流れ / 階層 / 2 軸）→
  図の有無を書いてから描く
- 図にするのは、関係か流れが見える節。並列の列挙は箇条書きのまま、形が言えない節には置かない
- 1 記事 3 枚まで。1 枚に描く仕組みは一つ
- 置く位置は、その節の発見が出そろった段落の後（先に出すと節の展開を先取りする。`zenn-format` の Figures と同じ規則を channel ごとに持つ）
- JA 稿の図は日本語、EN 稿の図は英語で作る。EN の語は EN 稿の本文の用語から取る

## 図の決まり

- 1200×1200 の正方形の SVG。地は `#FAFAF7`、文字と線は `#242321`、強調の色は記事ごとに一つ（既定 `#C65F38`）。
  使う色はこの三つ
- 上に小さく記事の題（強調の色、36px）、その下に図の題（Noto Serif CJK JP の bold、60px）。図の題は仕組みの名前にする
- 箱、線、矢印、ラベルで描く。写真や絵は使わない
- いちばん小さい文字でも 36px 以上、箱の中の文字は 42px 以上（英語で幅が足りないときは 36px まで）。線は 5px、
  強調の線は 7px、左右の余白は 60px。図は記事の幅（600〜730px）まで縮んで表示されるので、これより細い字と線は読めない
- 図の中の文字は、題を除いて日本語でおよそ 60 字、英語でおよそ 30 語まで。入りきらなければ仕組みの芯でない言葉を削る
- 書体は Noto Sans CJK JP と Noto Serif CJK JP。太さは `font-weight="500"` を基本にし、図の題、小見出し、図の中の強調の色の
  文字は `bold`。上の小さな記事の題は 500 のまま
- 題、地の rect、defs の中を除く要素に、現れる順の番号を `data-step="1"` のように付ける。1 からの連番で 5〜12 段。
  一緒に読むもの（箱とその中の文字、矢印とその名前）は同じ番号にする。順番は、その仕組みを言葉で説明するときの順
  （原因から結果、前提から帰結）で、本文の説明の順と合わせる
- 番号は text、rect、line、circle などの要素に付け、tspan には付けない（tspan が消えると後ろの文字が詰まる）。
  矢印は line で描く（動画で伸びるのは line だけ）
- 図の言葉と事実は本文から取る。本文に無い人名、年、数値、評価は足さない
- 本文の限定（「いくらか」「一部の」）と確度は、短くしても残す。本文が著者の読みとして出していることを図に
  するときは、図の中にその印を入れる（例: 「この文章の読み」）。本文が「Aの達成」と言うものを「A」に縮めると
  指すものが変わる

決まりどおりに描いた見本は `figures/sectarian-dispute-failure-of-buddhism-championship.svg`（日本語）と
`-championship-en.svg`（英語）。大きさ、太さ、番号の付け方はこれに合わせる。

## 作る

SVG は `figures/<slug>-<what>.svg`（EN は `-en.svg`）に置く。repo の根で:

```bash
uv run --project scripts python scripts/animate_figure.py figures/<slug>-<what>.svg <scratch>/<what>.mp4 \
  --sheet <scratch>/<what>.sheet.png --gif images/<slug>-<what>.gif
```

- `--sheet` の PNG は、番号ごとに現れきったコマを順に並べた 1 枚。Read で開き、現れる順が説明の順になっているか、
  どのコマにも文字の化け、欠け、はみ出し、重なりが無いかを見て、あれば SVG を直して回し直す
- `--gif` の GIF が本文に置く成果物（一辺 900px、最後のコマで 8 秒止まって繰り返す）。MP4 は SNS の告知に使える
- 道具は `rsvg-convert` と `ffmpeg`（Homebrew の `librsvg` と `ffmpeg`）、書体は Noto Sans / Serif CJK JP

## 照合してから著者に見せる

1. 図の文字と本文の照合を、描いた session と別の process に渡す（`fact-checker`、無い session では read-only の
   subagent）。渡すのは SVG と原稿の path と、図と節の対応。見てもらうのは、本文に無い事実を足していないか、
   限定や確度を落としていないか、矢印の向きが本文と合うか、JA と EN の図が同じ内容か、現れる順が本文の順と
   矛盾しないか。確信の高い指摘は反映し、処分を記録に残す
2. 直した GIF を著者に見せる（JA と EN の両方。SendUserFile で送り、その道具が無い session では GIF の path を渡す）。
   図を媒体に入れるのは著者が見た後
3. 原稿に行を足す。`![<図が示すこと 1 文>](/images/<slug>-<what>.gif)` を、対応する段落の後に空行をはさんで置く。
   alt の 1 文は図の中の文字ではなく、図が示すことを書く

SVG の正本はこの repo の `figures/` に置く（道具がここにあるため）。論考の正本が別のリポジトリにあるとき
（例: `attention-not-self`）は、できあがった SVG と GIF をそのリポジトリの `figures/` に写し、その原稿から相対パスで
参照する。写した先の名前はそのリポジトリの付け方に従う（例: `figures/contested-concepts-fig1-championship.gif`）。
図を直すときはこの repo の SVG を直し、GIF を作り直してから写し直す。この repo の `note/` と `substack/` の写しにも
同じ位置に行を足す。

## 媒体に入れる

- note: `note-publishing` の「本文の図（GIF）」。キャプションは付けない（読み戻しの本文一致を保つ）
- Substack: `substack-publishing` の「画像と本文の図」

図を足した稿は著者がもう一度通読する。図と alt の追加は構造変更ではないので、内容 GO とタイトル選択は
やり直さない（`writing-ecosystem` §4）。
