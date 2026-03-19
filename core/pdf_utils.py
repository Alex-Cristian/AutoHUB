from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT_NAME = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'

for regular_path, bold_path in [
    ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    ('/usr/share/fonts/dejavu/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf'),
]:
    if Path(regular_path).exists() and Path(bold_path).exists():
        pdfmetrics.registerFont(TTFont('DejaVuSans', regular_path))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', bold_path))
        FONT_NAME = 'DejaVuSans'
        FONT_BOLD = 'DejaVuSans-Bold'
        break


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='AutoTitle',
        parent=styles['Heading1'],
        fontName=FONT_BOLD,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#111111'),
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name='AutoHeading',
        parent=styles['Heading3'],
        fontName=FONT_BOLD,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#111111'),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name='AutoBody',
        parent=styles['BodyText'],
        fontName=FONT_NAME,
        fontSize=9.5,
        leading=12,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#222222'),
    ))
    styles.add(ParagraphStyle(
        name='AutoSmall',
        parent=styles['BodyText'],
        fontName=FONT_NAME,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#666666'),
    ))
    return styles


def _safe(value, default='—'):
    if value is None:
        return default
    value = str(value).strip()
    return value or default


def _paragraph(text, style):
    return Paragraph(_safe(text).replace('\n', '<br/>'), style)


def build_work_order_pdf(booking):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm, bottomMargin=14*mm)
    s = _styles()
    elements = []

    elements.append(Paragraph(f'Fișă intervenție service / raport intern #{booking.pk}', s['AutoTitle']))
    elements.append(Paragraph(
        'Document generat din AutoEMG pentru arhivarea lucrării și export PDF. '
        'Acest fișier nu reprezintă o transmitere automată către RAR.',
        s['AutoSmall'],
    ))
    elements.append(Spacer(1, 8))

    header_data = [
        [_paragraph('<b>Service</b><br/>' + _safe(booking.center.legal_name or booking.center.name), s['AutoBody']),
         _paragraph('<b>Data programării</b><br/>' + booking.booking_date.strftime('%d.%m.%Y'), s['AutoBody'])],
        [_paragraph('<b>Adresă</b><br/>' + _safe(booking.center.headquarters or booking.center.address), s['AutoBody']),
         _paragraph('<b>Ora</b><br/>' + booking.booking_time.strftime('%H:%M'), s['AutoBody'])],
        [_paragraph('<b>CIF / CUI</b><br/>' + _safe(booking.center.fiscal_code), s['AutoBody']),
         _paragraph('<b>Durată estimată</b><br/>' + booking.get_duration_display(), s['AutoBody'])],
    ]
    ht = Table(header_data, colWidths=[90*mm, 90*mm])
    ht.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(ht)
    elements.append(Spacer(1, 10))

    sections = [
        ('Date client', [
            ('Nume', booking.client_name),
            ('Telefon', booking.client_phone),
            ('Email', booking.client_email),
        ]),
        ('Date autovehicul', [
            ('Marcă / model', f'{booking.car_brand} {booking.car_model}'),
            ('An fabricație', booking.car_year),
            ('Combustibil', booking.get_car_fuel_display()),
            ('Număr înmatriculare', booking.car_plate),
            ('VIN', booking.car_vin),
        ]),
        ('Date intervenție', [
            ('Garaj', booking.garage.name if booking.garage_id else '—'),
            ('Serviciu selectat', booking.service_item.name if booking.service_item_id else '—'),
            ('Mecanic alocat', booking.mechanic.name if booking.mechanic_id else '—'),
            ('Status', booking.get_status_display()),
            ('Cost estimativ', f'{booking.estimated_price:.2f} RON' if booking.estimated_price is not None else '—'),
        ]),
    ]

    for title, rows in sections:
        elements.append(Paragraph(title, s['AutoHeading']))
        data = [[_paragraph(f'<b>{label}</b>', s['AutoBody']), _paragraph(str(value), s['AutoBody'])] for label, value in rows]
        table = Table(data, colWidths=[55*mm, 125*mm])
        table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e2e2')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 8))

    long_sections = [
        ('Descriere problemă', booking.problem_description),
        ('Servicii / piese folosite', booking.used_services or '—'),
        ('Descriere suplimentară', booking.additional_description or '—'),
        ('Note interne', booking.notes or '—'),
    ]
    for title, content in long_sections:
        elements.append(Paragraph(title, s['AutoHeading']))
        table = Table([[_paragraph(content, s['AutoBody'])]], colWidths=[180*mm])
        table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 8))

    sign = Table([
        [_paragraph('Semnătură service<br/><br/>__________________________', s['AutoBody']),
         _paragraph('Semnătură client<br/><br/>__________________________', s['AutoBody'])]
    ], colWidths=[90*mm, 90*mm])
    sign.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(Spacer(1, 10))
    elements.append(sign)

    doc.build(elements)
    return buffer.getvalue()


def build_invoice_pdf(invoice):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm, bottomMargin=14*mm)
    s = _styles()
    elements = []

    title = f'Factură #{invoice.invoice_no}' if invoice.invoice_no else 'Factură draft'
    elements.append(Paragraph(title, s['AutoTitle']))
    elements.append(Paragraph(
        'Document PDF generat din AutoEMG. Pentru raportare fiscală oficială, fiecare service rămâne '
        'responsabil de evidența contabilă și de integrarea separată cu e-Factura/ANAF, dacă este cazul.',
        s['AutoSmall'],
    ))
    elements.append(Spacer(1, 8))

    info = Table([
        [_paragraph(f'<b>Furnizor</b><br/>{_safe(invoice.company_name)}<br/>{_safe(invoice.company_address)}<br/>{_safe(invoice.company_city)}<br/>CIF: {_safe(invoice.company_fiscal_code)}<br/>Nr. RC: {_safe(invoice.company_trade_register_no)}', s['AutoBody']),
         _paragraph(f'<b>Client</b><br/>{_safe(invoice.client_name)}<br/>{_safe(invoice.client_address)}<br/>Tel: {_safe(invoice.client_phone)}<br/>Email: {_safe(invoice.client_email)}<br/>CIF: {_safe(invoice.client_fiscal_code)}', s['AutoBody'])],
        [_paragraph(f'<b>Data emiterii</b><br/>{invoice.issue_date.strftime("%d.%m.%Y")}', s['AutoBody']),
         _paragraph(f'<b>Status</b><br/>{invoice.get_status_display()}', s['AutoBody'])],
    ], colWidths=[90*mm, 90*mm])
    info.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e2e2')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(info)
    elements.append(Spacer(1, 10))

    lines = [[
        _paragraph('<b>Nr.</b>', s['AutoBody']),
        _paragraph('<b>Descriere</b>', s['AutoBody']),
        _paragraph('<b>Cant.</b>', s['AutoBody']),
        _paragraph('<b>Preț unitar</b>', s['AutoBody']),
        _paragraph('<b>Total</b>', s['AutoBody']),
    ]]
    for idx, line in enumerate(invoice.lines.all(), start=1):
        lines.append([
            _paragraph(str(idx), s['AutoBody']),
            _paragraph(line.description, s['AutoBody']),
            _paragraph(str(line.quantity), s['AutoBody']),
            _paragraph(f'{line.unit_price:.2f} RON', s['AutoBody']),
            _paragraph(f'{line.line_total:.2f} RON', s['AutoBody']),
        ])
    if len(lines) == 1:
        lines.append([_paragraph('—', s['AutoBody']) for _ in range(5)])

    lt = Table(lines, colWidths=[14*mm, 86*mm, 22*mm, 28*mm, 30*mm], repeatRows=1)
    lt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e2e2')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(lt)
    elements.append(Spacer(1, 10))

    totals = Table([
        [_paragraph('<b>Subtotal</b>', s['AutoBody']), _paragraph(f'{invoice.subtotal:.2f} RON', s['AutoBody'])],
        [_paragraph('<b>TVA</b>', s['AutoBody']), _paragraph('0.00 RON', s['AutoBody'])],
        [_paragraph('<b>Total</b>', s['AutoBody']), _paragraph(f'{invoice.total:.2f} RON', s['AutoBody'])],
    ], colWidths=[40*mm, 35*mm], hAlign='RIGHT')
    totals.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e2e2')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(totals)

    if invoice.notes:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph('Observații', s['AutoHeading']))
        nt = Table([[_paragraph(invoice.notes, s['AutoBody'])]], colWidths=[180*mm])
        nt.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')), ('PADDING', (0, 0), (-1, -1), 6)]))
        elements.append(nt)

    doc.build(elements)
    return buffer.getvalue()
