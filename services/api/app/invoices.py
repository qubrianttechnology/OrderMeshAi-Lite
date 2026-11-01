from hashlib import sha256
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import settings


def invoice_pdf(order, lines, organization, payments=None, returned=0):
    font_path = (
        Path(settings.invoice_font_path)
        if settings.invoice_font_path
        else Path(__file__).parent / "fonts" / "NotoSansSinhala.ttf"
    )
    if not font_path.is_file():
        raise ValueError("Invoice font is unavailable; check INVOICE_FONT_PATH")
    # Different configured font files must not reuse a previously registered face.
    font = (
        "InvoiceUnicode_" + sha256(str(font_path.resolve()).encode()).hexdigest()[:16]
    )
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, str(font_path), shapable=True))
    fonts = [font]
    if not settings.invoice_font_path:
        tamil_path = Path(__file__).parent / "fonts" / "NotoSansTamil.ttf"
        tamil_font = "InvoiceTamil"
        if tamil_font not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(tamil_font, str(tamil_path), shapable=True))
        fonts.append(tamil_font)

    def font_for(char):
        return next(
            (
                name
                for name in fonts
                if ord(char) in pdfmetrics.getFont(name).face.charWidths
            ),
            None,
        )

    texts = [
        organization.name,
        order.customer_name,
        order.customer_address,
        order.delivery_instructions or "",
        *[x.product_name for x in lines],
    ]
    if any(
        font_for(char) is None
        for text in texts
        for char in text
        if not char.isspace() and char not in "\u200c\u200d"
    ):
        raise ValueError(
            "Invoice font does not support all characters; configure INVOICE_FONT_PATH "
            "with a font that covers this invoice's languages"
        )
    output = BytesIO()
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = font
        style.shaping = True
        if hasattr(style, "leading"):
            style.leading = max(style.leading, style.fontSize * 1.6)

    def p(value):
        runs = []
        current_font = font
        current_text = ""
        for char in str(value):
            chosen = current_font if char in "\u200c\u200d" else font_for(char) or font
            if chosen != current_font:
                runs.append(
                    f'<font name="{current_font}">{escape(current_text)}</font>'
                )
                current_text = ""
                current_font = chosen
            current_text += char
        runs.append(f'<font name="{current_font}">{escape(current_text)}</font>')
        return Paragraph("".join(runs).replace("\n", "<br/>"), styles["Normal"])

    story = [
        Paragraph(
            "PAYMENT RECORD" if payments is not None else "INVOICE", styles["Title"]
        ),
        p(organization.name),
        Spacer(1, 16),
        p(f"Order {order.id}"),
        p(f"Issued: {order.created_at.date()} | Currency: LKR"),
        p(f"Status: {order.status}"),
        Spacer(1, 12),
        p(order.customer_name),
        p(order.customer_address),
        p(f"Delivery instructions: {order.delivery_instructions}")
        if order.delivery_instructions
        else Spacer(1, 0),
        Spacer(1, 20),
    ]
    data = [[p("Product"), p("Qty"), p("Unit LKR"), p("Total LKR")]]
    for line in lines:
        data.append(
            [
                p(line.product_name),
                str(line.quantity),
                f"{line.price_minor / 100:,.2f}",
                f"{line.quantity * line.price_minor / 100:,.2f}",
            ]
        )
    table = Table(data, colWidths=[245, 45, 90, 95], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f4ef")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d9e3dd")),
            ]
        )
    )
    story.extend(
        [
            table,
            Spacer(1, 20),
            Paragraph(f"Total: LKR {order.total_minor / 100:,.2f}", styles["Heading2"]),
            p(
                f"Subtotal: LKR {getattr(order, 'subtotal_minor', order.total_minor) / 100:,.2f} | Discount: LKR {getattr(order, 'discount_minor', 0) / 100:,.2f} | Tax ({getattr(order, 'tax_basis_points', 0) / 100:g}%): LKR {getattr(order, 'tax_minor', 0) / 100:,.2f}"
            ),
            p(
                "This invoice is not proof of payment. Payments are recorded separately."
            ),
        ]
    )
    if payments is not None:
        received = sum(
            x.amount_minor if x.kind == "payment" else -x.amount_minor for x in payments
        )
        remaining = order.total_minor - returned - received
        story.extend(
            [
                Spacer(1, 12),
                p(f"Returns credited: LKR {returned / 100:,.2f}"),
                p(f"Net payments recorded: LKR {received / 100:,.2f}"),
                p(
                    f"Outstanding: LKR {max(remaining, 0) / 100:,.2f} | Refund due: LKR {max(-remaining, 0) / 100:,.2f}"
                ),
            ]
        )
        for payment in payments:
            story.append(
                p(
                    f"{payment.created_at.date()} | {payment.kind} | {payment.method} | LKR {payment.amount_minor / 100:,.2f}"
                )
            )
        story.append(
            p(
                "Payments shown are recorded by your workspace; this document does not confirm bank settlement."
            )
        )
    SimpleDocTemplate(output).build(story)
    return output.getvalue()
