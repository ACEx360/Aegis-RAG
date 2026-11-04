"""build_report.py — AegisRAG B.Tech Project Report Builder.

Reads chapter .md files and the front matter file, applies VIIT format
rules exactly, and produces report/AegisRAG_Report.docx using python-docx.

Format rules applied:
  - A4 page size.
  - Margins: top 23.4 mm, left 37 mm, bottom 32 mm, right 23.4 mm.
  - Body: Times New Roman 12 pt, justified, 1.5 line spacing,
    ~5-space (1.27 cm) first-line indent, space_after = 12 pt
    (blank line between paragraphs).
  - Chapter titles: TNR 14 pt bold, ALL CAPS, centred.
  - Section headings: TNR 12 pt bold, ALL CAPS, left.
  - Subheadings: TNR 12 pt bold, Title Case, left.
  - Footer: "Department of Computer Engineering, VIIT. 2026-27"
    10 pt centred, page number centred below.
  - Front matter: lower Roman numerals (i, ii, iii ...).
  - Main text (Chapter 1 onward): Arabic numerals starting at 1.
  - Figure captions BELOW figure placeholder: "Figure N.M: Title" 12 pt centred.
    Legend below caption at 10 pt centred.
  - Table captions: "Table N.M: Title" 12 pt centred, above table body.
  - TOC, List of Figures, List of Tables: Word field codes so that
    Ctrl+A, F9 updates page numbers after opening in Word.
  - References: IEEE numbered style, printed verbatim from 12_references.md.

Usage:
    uv run python report/build_report.py

Dependencies (already in project venv via uv):
    python-docx

Page-count estimation:
  - At Times New Roman 12 pt, 1.5 line spacing, space_after=12pt,
    with A4 margins (left 37mm, right 23.4mm → text width ~149mm ≈ 8.5in),
    a page holds approximately 280–300 words.
  - The script reports an estimated page count per chapter at the end.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

REPORT_DIR = Path(__file__).resolve().parent
CHAPTERS_DIR = REPORT_DIR / "chapters"
FIGURES_DIR = REPORT_DIR / "figures"
FIGURES_JSON = REPORT_DIR / "figures.json"
TABLES_JSON = REPORT_DIR / "tables.json"
OUTPUT_DOCX = REPORT_DIR / "AegisRAG_Report.docx"

WORDS_PER_PAGE = 290  # conservative midpoint for budget estimates

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FONT_BODY = "Times New Roman"
FONT_SIZE_BODY = Pt(12)
FONT_SIZE_CHAPTER = Pt(14)
FONT_SIZE_SECTION = Pt(12)
FONT_SIZE_FOOTER = Pt(10)
FONT_SIZE_LEGEND = Pt(10)

MARGIN_TOP = Mm(23.4)
MARGIN_LEFT = Mm(37)
MARGIN_BOTTOM = Mm(32)
MARGIN_RIGHT = Mm(23.4)

FOOTER_TEXT = "Department of Computer Engineering, VIIT. 2026-27"

# Chapter files in rendering order (front matter first, then Ch 1-9 + appendices)
CHAPTER_FILES = [
    "00_front_matter.md",
    "01_introduction.md",
    "02_literature_survey.md",
    "03_srs.md",
    "04_system_design.md",
    "05_project_plan.md",
    "06_implementation.md",
    "07_testing.md",
    "08_results.md",
    "09_conclusions.md",
    "10_appendices.md",
    "11_references.md",
]

# Page budgets (chapters 1-9 + appendices)
PAGE_BUDGET: dict[str, int] = {
    "01_introduction.md": 5,
    "02_literature_survey.md": 7,
    "03_srs.md": 8,
    "04_system_design.md": 10,
    "05_project_plan.md": 5,
    "06_implementation.md": 9,
    "07_testing.md": 5,
    "08_results.md": 6,
    "09_conclusions.md": 3,
}


# ---------------------------------------------------------------------------
# Section / page helpers
# ---------------------------------------------------------------------------

def _set_page_margins(section) -> None:
    """Apply VIIT A4 margins to a document section."""
    section.page_height = Mm(297)
    section.page_width = Mm(210)
    section.top_margin = MARGIN_TOP
    section.left_margin = MARGIN_LEFT
    section.bottom_margin = MARGIN_BOTTOM
    section.right_margin = MARGIN_RIGHT


def _add_footer(section, page_num_style: str = "DECIMAL") -> None:
    """Add the VIIT footer: department name (10pt centred) then page number.

    page_num_style: 'LOWERROMAN' for front matter, 'DECIMAL' for main text.
    This follows the Word PAGE field format switch (\\* LOWERROMAN / \\* DECIMAL).
    """
    footer = section.footer
    footer.is_linked_to_previous = False

    # Clear any pre-existing paragraphs
    for p in list(footer.paragraphs):
        p._element.getparent().remove(p._element)

    def _centred_para(parent_elem):
        p = OxmlElement("w:p")
        pPr = OxmlElement("w:pPr")
        jc = OxmlElement("w:jc")
        jc.set(qn("w:val"), "center")
        pPr.append(jc)
        p.append(pPr)
        parent_elem.append(p)
        return p

    def _text_run(p_elem, text, pt_size):
        r = OxmlElement("w:r")
        rPr = OxmlElement("w:rPr")
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(pt_size * 2)))
        sz_cs = OxmlElement("w:szCs")
        sz_cs.set(qn("w:val"), str(int(pt_size * 2)))
        rFonts = OxmlElement("w:rFonts")
        rFonts.set(qn("w:ascii"), FONT_BODY)
        rFonts.set(qn("w:hAnsi"), FONT_BODY)
        rPr.append(rFonts)
        rPr.append(sz)
        rPr.append(sz_cs)
        r.append(rPr)
        t = OxmlElement("w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = text
        r.append(t)
        p_elem.append(r)

    def _page_field_run(p_elem, style, pt_size):
        """Insert a PAGE field run into p_elem."""
        # begin
        r_begin = OxmlElement("w:r")
        rPr = OxmlElement("w:rPr")
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(pt_size * 2)))
        sz_cs = OxmlElement("w:szCs")
        sz_cs.set(qn("w:val"), str(int(pt_size * 2)))
        rPr.append(sz)
        rPr.append(sz_cs)
        r_begin.append(rPr)
        fc = OxmlElement("w:fldChar")
        fc.set(qn("w:fldCharType"), "begin")
        r_begin.append(fc)
        p_elem.append(r_begin)
        # instrText
        r_instr = OxmlElement("w:r")
        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = f" PAGE \\* {style} "
        r_instr.append(instr)
        p_elem.append(r_instr)
        # end
        r_end = OxmlElement("w:r")
        fc2 = OxmlElement("w:fldChar")
        fc2.set(qn("w:fldCharType"), "end")
        r_end.append(fc2)
        p_elem.append(r_end)

    # python-docx 1.x uses ._element; older versions used ._p
    fp = footer._element if hasattr(footer, "_element") else footer._p
    p1 = _centred_para(fp)
    _text_run(p1, FOOTER_TEXT, FONT_SIZE_FOOTER.pt)

    p2 = _centred_para(fp)
    _page_field_run(p2, page_num_style, FONT_SIZE_FOOTER.pt)


def _new_section(doc: Document, start_type=WD_SECTION_START.NEW_PAGE,
                  page_num_style: str = "DECIMAL") -> None:
    """Add a new section with the given page-break type and footer style."""
    sec = doc.add_section(start_type)
    _set_page_margins(sec)
    _add_footer(sec, page_num_style=page_num_style)


# ---------------------------------------------------------------------------
# Typography helpers
# ---------------------------------------------------------------------------

def _run_font(run, size_pt: float, bold: bool = False, italic: bool = False,
              color_rgb=None) -> None:
    """Apply font properties to a run."""
    run.font.name = FONT_BODY
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    if color_rgb:
        run.font.color.rgb = RGBColor(*color_rgb)


def _body_para_fmt(para, indent: bool = True) -> None:
    """Apply standard VIIT body paragraph formatting."""
    pf = para.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    if indent:
        pf.first_line_indent = Cm(1.27)
    pf.space_after = Pt(12)
    pf.space_before = Pt(0)


def add_chapter_heading(doc: Document, text: str) -> None:
    """Chapter title: TNR 14pt bold ALL CAPS centred."""
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_before = Pt(18)
    para.paragraph_format.space_after = Pt(18)
    run = para.add_run(text.upper())
    _run_font(run, 14, bold=True)


def add_section_heading(doc: Document, text: str) -> None:
    """Section heading: TNR 12pt bold ALL CAPS left."""
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    para.paragraph_format.space_before = Pt(14)
    para.paragraph_format.space_after = Pt(6)
    run = para.add_run(text.upper())
    _run_font(run, 12, bold=True)


def add_subheading(doc: Document, text: str) -> None:
    """Subheading: TNR 12pt bold Title Case left."""
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    para.paragraph_format.space_before = Pt(8)
    para.paragraph_format.space_after = Pt(4)
    run = para.add_run(text)
    _run_font(run, 12, bold=True)


def add_body_paragraph(doc: Document, text: str, indent: bool = True) -> None:
    """Body paragraph with VIIT formatting, stripping leading indent whitespace."""
    clean = text.lstrip()
    if not clean:
        return
    para = doc.add_paragraph()
    _body_para_fmt(para, indent=indent)
    # Handle inline bold **...**
    parts = re.split(r"(\*\*[^*]+\*\*)", clean)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = para.add_run(part[2:-2])
            _run_font(run, 12, bold=True)
        else:
            run = para.add_run(part)
            _run_font(run, 12)


def add_bullet_paragraph(doc: Document, text: str) -> None:
    """Bullet/list item: no first-line indent, hanging indent, body font."""
    clean = text.lstrip("- •\t").strip()
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    para.paragraph_format.left_indent = Cm(1.0)
    para.paragraph_format.first_line_indent = Cm(-0.5)
    para.paragraph_format.space_after = Pt(4)
    # Bullet character
    parts = re.split(r"(\*\*[^*]+\*\*)", clean)
    first = True
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = para.add_run(("• " if first else "") + part[2:-2])
            _run_font(run, 12, bold=True)
        else:
            run = para.add_run(("• " if first else "") + part)
            _run_font(run, 12)
        first = False


def add_numbered_item(doc: Document, text: str, num: int) -> None:
    """Numbered list item."""
    clean = re.sub(r"^\d+\.\s*", "", text.strip())
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    para.paragraph_format.left_indent = Cm(1.5)
    para.paragraph_format.first_line_indent = Cm(-1.0)
    para.paragraph_format.space_after = Pt(6)
    prefix_run = para.add_run(f"{num}. ")
    _run_font(prefix_run, 12, bold=False)
    parts = re.split(r"(\*\*[^*]+\*\*)", clean)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = para.add_run(part[2:-2])
            _run_font(run, 12, bold=True)
        else:
            run = para.add_run(part)
            _run_font(run, 12)


def _find_figure_png(fig_id: str) -> Path | None:
    """Search for a rendered PNG for the given figure ID in report/figures/.

    The fig_id is like '1.1', '4.3', etc.  PNG files are named like
    'fig1_1_overview.png'.  We map by replacing '.' with '_' and searching
    for a file whose name starts with f'fig{fig_id.replace(".", "_")}' or
    f'fig{chapter}_{section}_*.png'.
    """
    prefix = "fig" + fig_id.replace(".", "_")
    for png in FIGURES_DIR.glob("*.png"):
        if png.stem.startswith(prefix):
            return png
    return None


def add_figure_placeholder(doc: Document, fig_id: str, caption: str,
                            legend: str = "") -> None:
    """Insert a figure (PNG if available, grey placeholder otherwise) + caption + legend.

    Tries to embed the rendered PNG from report/figures/figN_M_*.png at
    15 cm width (approximately 300 dpi for an 1800-px-wide image).
    Falls back to a grey shaded placeholder paragraph if no PNG is found.
    Caption is always placed BELOW the figure as per VIIT format rules.
    """
    png_path = _find_figure_png(fig_id)

    if png_path and png_path.exists():
        # Embed the real rendered diagram
        img_para = doc.add_paragraph()
        img_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        img_para.paragraph_format.space_before = Pt(8)
        img_para.paragraph_format.space_after = Pt(4)
        run = img_para.add_run()
        run.add_picture(str(png_path), width=Cm(15))
    else:
        # Fallback: grey shaded placeholder
        ph = doc.add_paragraph()
        ph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ph.paragraph_format.space_before = Pt(8)
        ph.paragraph_format.space_after = Pt(4)
        pPr = ph._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "D9D9D9")
        pPr.append(shd)
        ph_run = ph.add_run(f"[Figure {fig_id} — PNG not found in report/figures/]")
        _run_font(ph_run, 10, italic=True, color_rgb=(0x60, 0x60, 0x60))

    # Caption BELOW (VIIT rule)
    cap_para = doc.add_paragraph()
    cap_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap_para.paragraph_format.space_before = Pt(2)
    cap_para.paragraph_format.space_after = Pt(2)
    cap_run = cap_para.add_run(f"Figure {fig_id}: {caption}")
    _run_font(cap_run, 12, bold=False)

    # Legend (10pt) below caption
    if legend:
        leg_para = doc.add_paragraph()
        leg_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        leg_para.paragraph_format.space_before = Pt(0)
        leg_para.paragraph_format.space_after = Pt(12)
        leg_run = leg_para.add_run(legend)
        _run_font(leg_run, 10)


def add_table_caption(doc: Document, tbl_id: str, caption: str) -> None:
    """Table caption above the table."""
    cap_para = doc.add_paragraph()
    cap_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap_para.paragraph_format.space_before = Pt(12)
    cap_para.paragraph_format.space_after = Pt(4)
    cap_run = cap_para.add_run(f"Table {tbl_id}: {caption}")
    _run_font(cap_run, 12, bold=False)


def add_simple_table(doc: Document, rows: list[list[str]]) -> None:
    """Add a simple plain table from a list of rows (first row = header)."""
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    tbl = doc.add_table(rows=len(rows), cols=ncols)
    tbl.style = "Table Grid"
    for i, row in enumerate(rows):
        for j, cell_text in enumerate(row):
            cell = tbl.rows[i].cells[j]
            cell.text = ""
            para = cell.paragraphs[0]
            para.paragraph_format.space_before = Pt(2)
            para.paragraph_format.space_after = Pt(2)
            run = para.add_run(cell_text)
            _run_font(run, 10, bold=(i == 0))
    doc.add_paragraph()  # spacing after table


# ---------------------------------------------------------------------------
# Word field helpers
# ---------------------------------------------------------------------------

def _insert_field(doc: Document, field_instruction: str, note: str = "") -> None:
    """Insert a Word field code paragraph."""
    para = doc.add_paragraph()
    run = para.add_run()
    fb = OxmlElement("w:fldChar")
    fb.set(qn("w:fldCharType"), "begin")
    fb.set(qn("w:dirty"), "true")
    run._r.append(fb)

    r2 = OxmlElement("w:r")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = field_instruction
    r2.append(instr)
    para._p.append(r2)

    r3 = OxmlElement("w:r")
    fe = OxmlElement("w:fldChar")
    fe.set(qn("w:fldCharType"), "end")
    r3.append(fe)
    para._p.append(r3)

    if note:
        note_p = doc.add_paragraph()
        note_run = note_p.add_run(note)
        _run_font(note_run, 9, italic=True, color_rgb=(0x80, 0x80, 0x80))


def add_toc_field(doc: Document) -> None:
    _insert_field(
        doc,
        ' TOC \\o "1-3" \\h \\z \\u ',
        "[Right-click → Update Field, or press Ctrl+A then F9, to populate page numbers.]",
    )


def add_lof_field(doc: Document) -> None:
    _insert_field(
        doc,
        " TOC \\h \\z \\c \"Figure\" ",
        "[Right-click → Update Field to populate List of Figures page numbers.]",
    )


def add_lot_field(doc: Document) -> None:
    _insert_field(
        doc,
        " TOC \\h \\z \\c \"Table\" ",
        "[Right-click → Update Field to populate List of Tables page numbers.]",
    )


# ---------------------------------------------------------------------------
# Markdown line parser
# ---------------------------------------------------------------------------

def _classify_line(line: str) -> tuple[str, str]:
    """Return (kind, content) for a markdown line.

    Kinds: chapter_heading, section_heading, subheading, sub2heading,
           figure_marker, table_marker, bullet, numbered_item,
           separator, comment, blank, body, raw_table_row, legend_line.
    """
    stripped = line.rstrip("\n")

    # HTML comments
    if stripped.startswith("<!--") or stripped.endswith("-->"):
        return "comment", stripped

    # Legend lines (lines starting with "Legend:")
    if stripped.lstrip().startswith("Legend:"):
        return "legend_line", stripped.strip()

    # Horizontal rule
    if re.match(r"^---+$", stripped.strip()):
        return "separator", ""

    # Chapter heading: # CHAPTER ...
    if re.match(r"^#\s+CHAPTER\s+", stripped, re.IGNORECASE):
        return "chapter_heading", re.sub(r"^#+\s*", "", stripped).strip()

    # Front matter special headings: # TITLE (single hash, not chapter)
    if re.match(r"^#\s+[A-Z]", stripped) and not stripped.startswith("##"):
        return "chapter_heading", re.sub(r"^#+\s*", "", stripped).strip()

    # Section heading: ## N.N ...
    if re.match(r"^##\s+\d+\.\d+", stripped):
        return "section_heading", re.sub(r"^#+\s*", "", stripped).strip()

    # Section heading: ## non-numbered (Appendix, etc.)
    if re.match(r"^##\s+[A-Z]", stripped):
        return "section_heading", re.sub(r"^#+\s*", "", stripped).strip()

    # Subheading: ### N.N.N ...
    if re.match(r"^###\s+\d+\.\d+\.\d+", stripped):
        return "subheading", re.sub(r"^#+\s*", "", stripped).strip()

    # Subheading: ### other
    if re.match(r"^###\s+", stripped):
        return "subheading", re.sub(r"^#+\s*", "", stripped).strip()

    # Sub-sub heading: #### ...
    if re.match(r"^####\s+", stripped):
        return "sub2heading", re.sub(r"^#+\s*", "", stripped).strip()

    # Figure marker: [Figure N.M: Caption]
    if re.match(r"^\[Figure\s+[\d\.]+:", stripped):
        m = re.match(r"^\[Figure\s+([\d\.]+):\s*(.*?)\]", stripped)
        if m:
            return "figure_marker", m.group(1) + "|" + m.group(2)

    # Figure caption lines (bare "Figure N.M: Title" not in brackets)
    if re.match(r"^Figure\s+[\d\.]+:", stripped):
        return "comment", stripped  # skip — caption emitted by figure_marker

    # Table marker: [Table N.M: Caption]
    if re.match(r"^\[Table\s+[\d\.]+:", stripped):
        m = re.match(r"^\[Table\s+([\d\.]+):\s*(.*?)\]", stripped)
        if m:
            return "table_marker", m.group(1) + "|" + m.group(2)

    # Markdown table row
    if stripped.lstrip().startswith("|"):
        return "raw_table_row", stripped

    # Bullet
    if re.match(r"^\s*[-*]\s+", stripped):
        return "bullet", stripped

    # Numbered item
    if re.match(r"^\s*\d+\.\s+", stripped):
        return "numbered_item", stripped

    # Blank
    if not stripped.strip():
        return "blank", ""

    # Default: body
    return "body", stripped


def parse_md_file(path: Path) -> list[tuple[str, str]]:
    """Parse a markdown file into a list of (kind, content) tuples."""
    lines = path.read_text(encoding="utf-8").splitlines()
    tokens: list[tuple[str, str]] = []

    # Collect raw table rows into groups
    i = 0
    while i < len(lines):
        kind, content = _classify_line(lines[i])

        if kind == "raw_table_row":
            # Collect all contiguous table rows
            table_rows_raw: list[str] = []
            while i < len(lines):
                k, _ = _classify_line(lines[i])
                if k == "raw_table_row":
                    table_rows_raw.append(lines[i].rstrip())
                    i += 1
                else:
                    break
            tokens.append(("table_block", "\n".join(table_rows_raw)))
        else:
            tokens.append((kind, content))
            i += 1

    return tokens


def parse_markdown_table(raw: str) -> list[list[str]]:
    """Parse a raw markdown table into a list of cell-string rows."""
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or set(line.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")) == set():
            continue  # separator row
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
    return rows


# ---------------------------------------------------------------------------
# Front matter renderer
# ---------------------------------------------------------------------------

def render_front_matter(doc: Document, path: Path) -> None:
    """Render the 00_front_matter.md file with Roman-numeral page style."""
    tokens = parse_md_file(path)

    i = 0
    while i < len(tokens):
        kind, content = tokens[i]

        if kind == "comment":
            # Extract legend from source comment if applicable
            i += 1
            continue

        if kind == "separator":
            doc.add_page_break()
            i += 1
            continue

        if kind == "blank":
            i += 1
            continue

        if kind == "chapter_heading":
            add_chapter_heading(doc, content)
            i += 1
            continue

        if kind == "section_heading":
            add_section_heading(doc, content)
            i += 1
            continue

        if kind == "subheading":
            add_subheading(doc, content)
            i += 1
            continue

        if kind == "figure_marker":
            fig_id, caption = content.split("|", 1)
            # Look ahead for legend
            legend = ""
            if i + 1 < len(tokens) and tokens[i + 1][0] == "legend_line":
                legend = tokens[i + 1][1]
                i += 1
            add_figure_placeholder(doc, fig_id, caption, legend)
            i += 1
            continue

        if kind == "legend_line":
            # Already consumed in figure_marker look-ahead
            i += 1
            continue

        if kind == "table_marker":
            tbl_id, caption = content.split("|", 1)
            add_table_caption(doc, tbl_id, caption)
            i += 1
            continue

        if kind == "table_block":
            rows = parse_markdown_table(content)
            if rows:
                add_simple_table(doc, rows)
            i += 1
            continue

        if kind == "bullet":
            add_bullet_paragraph(doc, content)
            i += 1
            continue

        if kind == "numbered_item":
            # Extract number
            m = re.match(r"^\s*(\d+)\.\s+", content)
            num = int(m.group(1)) if m else 1
            add_numbered_item(doc, content, num)
            i += 1
            continue

        if kind == "body":
            add_body_paragraph(doc, content)
            i += 1
            continue

        i += 1


# ---------------------------------------------------------------------------
# Chapter renderer (for Ch 1-9, appendices, references)
# ---------------------------------------------------------------------------

def render_chapter(doc: Document, path: Path) -> int:
    """Render a chapter file. Returns estimated word count."""
    tokens = parse_md_file(path)
    word_count = 0
    first_chapter_heading = True

    i = 0
    while i < len(tokens):
        kind, content = tokens[i]

        if kind in ("comment",):
            i += 1
            continue

        if kind == "separator":
            i += 1
            continue

        if kind == "blank":
            i += 1
            continue

        if kind == "chapter_heading":
            if first_chapter_heading:
                first_chapter_heading = False
            add_chapter_heading(doc, content)
            i += 1
            continue

        if kind == "section_heading":
            add_section_heading(doc, content)
            i += 1
            continue

        if kind == "subheading":
            add_subheading(doc, content)
            i += 1
            continue

        if kind == "sub2heading":
            add_subheading(doc, content)
            i += 1
            continue

        if kind == "figure_marker":
            fig_id, caption = content.split("|", 1)
            legend = ""
            if i + 1 < len(tokens) and tokens[i + 1][0] == "legend_line":
                legend = tokens[i + 1][1]
                i += 1
            add_figure_placeholder(doc, fig_id, caption, legend)
            i += 1
            continue

        if kind == "legend_line":
            i += 1
            continue

        if kind == "table_marker":
            tbl_id, caption = content.split("|", 1)
            add_table_caption(doc, tbl_id, caption)
            i += 1
            continue

        if kind == "table_block":
            rows = parse_markdown_table(content)
            if rows:
                add_simple_table(doc, rows)
            i += 1
            continue

        if kind == "bullet":
            word_count += len(content.split())
            add_bullet_paragraph(doc, content)
            i += 1
            continue

        if kind == "numbered_item":
            m = re.match(r"^\s*(\d+)\.\s+", content)
            num = int(m.group(1)) if m else 1
            word_count += len(content.split())
            add_numbered_item(doc, content, num)
            i += 1
            continue

        if kind == "body":
            word_count += len(content.split())
            add_body_paragraph(doc, content)
            i += 1
            continue

        i += 1

    return word_count


# ---------------------------------------------------------------------------
# Front matter special pages
# ---------------------------------------------------------------------------

def _front_page_cover(doc: Document) -> None:
    """Render the cover page from 00_front_matter.md (already handled in render_front_matter)."""


def _insert_toc_pages(doc: Document) -> None:
    """Insert TOC, List of Figures, and List of Tables pages."""
    # TOC
    add_chapter_heading(doc, "TABLE OF CONTENTS")
    add_toc_field(doc)
    doc.add_page_break()

    # List of Figures
    add_chapter_heading(doc, "LIST OF FIGURES")
    add_lof_field(doc)
    doc.add_page_break()

    # List of Tables
    add_chapter_heading(doc, "LIST OF TABLES")
    add_lot_field(doc)
    doc.add_page_break()


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build() -> None:
    """Build AegisRAG_Report.docx from chapter markdown files."""
    doc = Document()

    # Remove the empty default paragraph that python-docx adds
    for para in list(doc.paragraphs):
        para._element.getparent().remove(para._element)

    # -----------------------------------------------------------------------
    # SECTION 1: Front matter — lower Roman numeral page numbers
    # -----------------------------------------------------------------------
    section0 = doc.sections[0]
    _set_page_margins(section0)
    _add_footer(section0, page_num_style="LOWERROMAN")

    # Render front matter (cover, certificate, acknowledgement, abstract, abbreviations)
    fm_path = CHAPTERS_DIR / "00_front_matter.md"
    if fm_path.exists():
        render_front_matter(doc, fm_path)
    else:
        add_chapter_heading(doc, "FRONT MATTER")
        add_body_paragraph(doc, "[00_front_matter.md not found]")

    doc.add_page_break()

    # TOC, LoF, LoT (still front matter — Roman numerals)
    _insert_toc_pages(doc)

    # -----------------------------------------------------------------------
    # SECTION 2: Main text — Arabic page numbers, restart at 1
    # -----------------------------------------------------------------------
    main_section = doc.add_section(WD_SECTION_START.NEW_PAGE)
    _set_page_margins(main_section)
    _add_footer(main_section, page_num_style="DECIMAL")

    # Restart page numbering at 1
    sect_pr = main_section._sectPr
    pg_num_type = OxmlElement("w:pgNumType")
    pg_num_type.set(qn("w:start"), "1")
    sect_pr.append(pg_num_type)

    # -----------------------------------------------------------------------
    # Chapters 1–9 + Appendices + References
    # -----------------------------------------------------------------------
    chapter_files = [
        "01_introduction.md",
        "02_literature_survey.md",
        "03_srs.md",
        "04_system_design.md",
        "05_project_plan.md",
        "06_implementation.md",
        "07_testing.md",
        "08_results.md",
        "09_conclusions.md",
        "10_appendices.md",
        "11_references.md",
    ]

    word_counts: dict[str, int] = {}
    first_chapter = True

    for fname in chapter_files:
        path = CHAPTERS_DIR / fname
        if not path.exists():
            print(f"  [SKIP] {fname} — file not found")
            continue

        if not first_chapter:
            doc.add_page_break()
        first_chapter = False

        wc = render_chapter(doc, path)
        word_counts[fname] = wc

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    doc.save(OUTPUT_DOCX)
    print(f"\nSaved: {OUTPUT_DOCX}\n")

    # -----------------------------------------------------------------------
    # Page count report
    # -----------------------------------------------------------------------
    print("Estimated page counts (at ~290 words/page):")
    print(f"  {'File':<35} {'Words':>6}  {'Est. pages':>10}  {'Budget':>8}  {'Status':>10}")
    print("  " + "-" * 75)
    total_main = 0
    for fname, wc in word_counts.items():
        if fname in ("10_appendices.md", "11_references.md"):
            budget_str = "—"
            status = ""
        else:
            budget = PAGE_BUDGET.get(fname, 0)
            budget_str = str(budget)
            est = wc / WORDS_PER_PAGE
            over = est - budget
            status = "OK" if over <= 1 else f"OVER +{over:.1f}"
        est = wc / WORDS_PER_PAGE
        total_main += wc if fname not in ("10_appendices.md", "11_references.md") else 0
        print(
            f"  {fname:<35} {wc:>6}  {est:>10.1f}  {budget_str:>8}  {status:>10}"
        )
    print("  " + "-" * 75)
    total_est = total_main / WORDS_PER_PAGE
    print(f"  {'TOTAL Ch1–9 estimated pages':<35}        {total_est:>10.1f}  {'50–60':>8}")
    print()
    print("IMPORTANT: Open the .docx in Word and press Ctrl+A then F9")
    print("(or right-click each field and choose 'Update Field') to populate")
    print("the Table of Contents, List of Figures, and List of Tables.")


if __name__ == "__main__":
    build()
