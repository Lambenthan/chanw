# Essay 配图 TikZ 源码

这些图用 TikZ 画、本地 TinyTeX 编译，字体 LXGW WenKai Light + Times New Roman，配色取自 src/global.css。

编译（绕开 Ghostscript，走 XeTeX 原生 xdv）：

    export PATH="$HOME/Library/TinyTeX/bin/universal-darwin:$PATH"
    xelatex -no-pdf cc-project.tex && dvisvgm cc-project.xdv --no-fonts -o cc-project.svg
    # 位图：xelatex cc-project.tex && pdftoppm -png -r 300 cc-project.pdf out

成品 PNG 落在 src/images/essays/（正文图）与 src/images/covers/（封面）。
