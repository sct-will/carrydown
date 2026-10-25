#!/usr/bin/env python3
"""Build small Word documents that exercise the renderer. Standard library only.

The self test runs this script into a temporary folder, so no binary file is kept in the
repository. Output is deterministic: the same arguments give the same bytes.

Modes
  paragraph  automatic heading numbers set on each heading paragraph (w:numPr), plus a
             footnote, tracked changes, a field, a smart tag, a block content control, a
             nested list, a table, a figure, a typed number, an unnumbered heading, a heading
             in a style with a non-English id and a heading marked only by its outline level.
  style      automatic heading numbers that come from the heading styles in styles.xml,
             the most common Word layout, with a level 2 list that restarts under each
             level 1 heading, and one heading that switches numbering off (numId 0).
  doctype    a document whose main part carries a DOCTYPE declaration. The renderer must
             refuse to parse it.
  doctype-late     the DOCTYPE after a comment longer than 4096 bytes.
  doctype-utf16    the main part in UTF-16 with a byte order mark, carrying a DOCTYPE.
  entity-styles    an ENTITY declaration in styles.xml, without a DOCTYPE line of its own.
  malformed  a main part that is not well-formed XML.
  nomedia    a figure whose image part is missing from the archive.
  dupfigures two figures captioned "Figure 1" with different images.

Usage
  python3 tests/fixtures/make_numbered_docx.py OUT.docx [MODE]

Based on the fixture builder written for the review of 2026-10-24.
"""
import base64
import sys
import zipfile

W = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
     'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
     'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
     'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
     'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')
DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def p(text, style=None, numid=None, ilvl=None, extra="", outline=None):
    ppr = ""
    if style or numid is not None or outline is not None:
        num = ""
        if numid is not None:
            num = "<w:numPr>" + (f'<w:ilvl w:val="{ilvl}"/>' if ilvl is not None else "") + f'<w:numId w:val="{numid}"/></w:numPr>'
        ppr = ("<w:pPr>" + (f'<w:pStyle w:val="{style}"/>' if style else "") + num
               + (f'<w:outlineLvl w:val="{outline}"/>' if outline is not None else "") + "</w:pPr>")
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{text}</w:t></w:r>{extra}</w:p>'


IMG = ('<w:p><w:r><w:drawing><wp:inline><wp:extent cx="1" cy="1"/><wp:docPr id="1" name="p"/><a:graphic>'
       '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:blipFill>'
       '<a:blip r:embed="rIdImg"/></pic:blipFill></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')


def style(sid, name, based=None, numid=None, ilvl=None, outline=None):
    ppr = ""
    if numid is not None or ilvl is not None or outline is not None:
        ppr = "<w:pPr>"
        if numid is not None or ilvl is not None:
            ppr += ("<w:numPr>" + (f'<w:ilvl w:val="{ilvl}"/>' if ilvl is not None else "")
                    + (f'<w:numId w:val="{numid}"/>' if numid is not None else "") + "</w:numPr>")
        if outline is not None:
            ppr += f'<w:outlineLvl w:val="{outline}"/>'
        ppr += "</w:pPr>"
    return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{name}"/>'
            + (f'<w:basedOn w:val="{based}"/>' if based else "") + ppr + "</w:style>")


def paragraph_mode():
    body = "".join([
        p("Design doc", "Title"),
        p("Overview", "Heading1", numid=9, ilvl=0),         # 1 Overview
        p("Scope", "Heading2", numid=9, ilvl=1),            # 1.1 Scope
        p("Body text with a footnote", extra='<w:r><w:footnoteReference w:id="1"/></w:r>'),
        '<w:p><w:r><w:t>Kept </w:t></w:r><w:del w:id="1" w:author="x"><w:r><w:delText>DELETED </w:delText></w:r></w:del>'
        '<w:ins w:id="2" w:author="x"><w:r><w:t>INSERTED</w:t></w:r></w:ins></w:p>',
        '<w:p><w:fldSimple w:instr="REF _Ref1 \\h"><w:r><w:t>Section-ref-in-field</w:t></w:r></w:fldSimple>'
        '<w:r><w:t xml:space="preserve"> and </w:t></w:r><w:smartTag w:uri="u" w:element="e"><w:r><w:t>SmartTagText</w:t></w:r></w:smartTag>'
        '<w:r><w:t xml:space="preserve"> and </w:t></w:r><w:moveTo w:id="3" w:author="x"><w:r><w:t>MovedText</w:t></w:r></w:moveTo>'
        '<w:moveFrom w:id="4" w:author="x"><w:r><w:t>OldPlace</w:t></w:r></w:moveFrom></w:p>',
        p("Architecture", "Heading1", numid=9, ilvl=0),     # 2 Architecture
        p("first numbered", None, numid=5, ilvl=0),
        p("nested bullet", None, numid=5, ilvl=1),
        p("second numbered", None, numid=5, ilvl=0),
        '<w:sdt><w:sdtPr/><w:sdtContent>' + p("Text inside a block content control") + '</w:sdtContent></w:sdt>',
        '<w:p><w:sdt><w:sdtContent><w:r><w:t>Inline control text</w:t></w:r></w:sdtContent></w:sdt></w:p>',
        '<w:tbl><w:tr><w:tc>' + p("Col A") + '</w:tc><w:tc>' + p("Col B") + '</w:tc></w:tr><w:tr><w:tc>'
        + p("a|pipe") + '</w:tc><w:tc>' + p("Plain cell") + '</w:tc></w:tr></w:tbl>',
        IMG,
        p("Figure 1: A picture"),
        p("3.4 Typed numbered heading", "Heading1"),
        p("Overview", "Heading1"),
        p("\u00dcberblick", "berschrift1"),                # a heading style whose id is not English
        p("Outline level heading", outline=0),
    ])
    styles = "".join([
        style("Normal", "Normal"),
        style("Title", "Title", "Normal"),
        style("Heading1", "heading 1", "Normal", outline=0),
        style("Heading2", "heading 2", "Normal", outline=1),
        style("berschrift1", "heading 1", "Normal", outline=0),
    ])
    numbering = (
        '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>'
        '<w:lvl w:ilvl="1"><w:numFmt w:val="bullet"/><w:lvlText w:val="o"/></w:lvl></w:abstractNum>'
        '<w:abstractNum w:abstractNumId="2"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1"/></w:lvl>'
        '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2"/></w:lvl></w:abstractNum>'
        '<w:num w:numId="5"><w:abstractNumId w:val="1"/></w:num><w:num w:numId="9"><w:abstractNumId w:val="2"/></w:num>'
    )
    footnotes = ('<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
                 '<w:footnote w:id="1"><w:p><w:r><w:t>The footnote text that is not rendered.</w:t></w:r></w:p></w:footnote>')
    return body, styles, numbering, footnotes


def style_mode():
    body = "".join([
        p("Numbered by style", "Title"),
        p("Overview", "Heading1"),                          # 1 Overview
        p("Scope", "Heading2"),                             # 1.1 Scope
        p("Goals", "Heading2"),                             # 1.2 Goals
        p("Architecture", "Heading1"),                      # 2 Architecture
        p("Data", "Heading2"),                              # 2.1 Data
        p("Interfaces", "Heading3"),                        # 2.1.1 Interfaces
        p("Appendix", "Heading1", numid=0),                 # numbering switched off on this paragraph
        p("Plain text after the appendix."),
    ])
    styles = "".join([
        style("Normal", "Normal"),
        style("Title", "Title", "Normal"),
        style("Heading1", "heading 1", "Normal", numid=7, ilvl=0, outline=0),
        style("Heading2", "heading 2", "Normal", numid=7, ilvl=1, outline=1),
        style("Heading3", "heading 3", "Heading2", ilvl=2, outline=2),   # numId inherited from Heading2
    ])
    numbering = (
        '<w:abstractNum w:abstractNumId="4">'
        '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="Heading1"/><w:lvlText w:val="%1"/></w:lvl>'
        '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="Heading2"/><w:lvlText w:val="%1.%2"/></w:lvl>'
        '<w:lvl w:ilvl="2"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="Heading3"/><w:lvlText w:val="%1.%2.%3"/></w:lvl>'
        '</w:abstractNum><w:num w:numId="7"><w:abstractNumId w:val="4"/></w:num>'
    )
    return body, styles, numbering, ""


def build(out, mode):
    if mode == "style":
        body, styles, numbering, footnotes = style_mode()
    else:
        body, styles, numbering, footnotes = paragraph_mode()
    doc = f"{DECL}<w:document {W}><w:body>{body}</w:body></w:document>"
    if mode == "doctype":
        doc = doc.replace(DECL, DECL + '<!DOCTYPE w:document [<!ENTITY a "aaaa">]>')
    if mode == "doctype-late":
        doc = doc.replace(DECL, DECL + "<!--" + "x" * 5000 + '--><!DOCTYPE w:document [<!ENTITY a "aaaa">]>')
    if mode == "malformed":
        doc = doc.replace("</w:body>", "<w:p></w:body>")
    if mode == "dupfigures":
        fig = ('<w:p><w:r><w:drawing><wp:inline><a:graphic><a:graphicData><pic:pic><pic:blipFill>'
               '<a:blip r:embed="{rid}"/></pic:blipFill></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
               '<w:p><w:r><w:t>Figure 1. {cap}</w:t></w:r></w:p>')
        doc = doc.replace("</w:body>", fig.format(rid="rIdImg", cap="First") + fig.format(rid="rIdImg2", cap="Second") + "</w:body>")
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdImg" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>'
            '<Relationship Id="rIdImg2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image2.png"/>'
            '<Relationship Id="rIdN" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>'
            '</Relationships>')
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    ct = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    parts = [
        ("[Content_Types].xml", ct),
        ("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                        '<Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'),
        ("word/document.xml", doc),
        ("word/styles.xml", f"{DECL}<w:styles {W}>{styles}</w:styles>"),
        ("word/numbering.xml", f"{DECL}<w:numbering {W}>{numbering}</w:numbering>"),
        ("word/_rels/document.xml.rels", rels),
        ("word/media/image1.png", png),
        ("word/media/image2.png", png + b"2"),
    ]
    if mode == "nomedia":
        parts = [x for x in parts if not x[0].startswith("word/media/")]
    if mode == "doctype-utf16":
        parts = [(n, (b"\xff\xfe" + d.replace(DECL, DECL.replace("UTF-8", "UTF-16") + '<!DOCTYPE w:document [<!ENTITY a "aaaa">]>').encode("utf-16-le"))
                  if n == "word/document.xml" else d) for n, d in parts]
    if mode == "entity-styles":
        parts = [(n, d.replace(DECL, DECL + '<!ENTITY a "aaaa">') if n == "word/styles.xml" else d) for n, d in parts]
    if footnotes:
        parts.append(("word/footnotes.xml", f"{DECL}<w:footnotes {W}>{footnotes}</w:footnotes>"))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data.encode("utf-8") if isinstance(data, str) else data)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if len(sys.argv) >= 2 else 2)
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "paragraph")
