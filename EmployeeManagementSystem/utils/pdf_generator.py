"""
PDF Generator Utility - Employee Management System
Generates professional, printable PDF salary slips using ReportLab.
"""

import io
import calendar
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def generate_payslip_pdf(payroll_record):
    """
    Builds a professional PDF payslip in memory and returns a BytesIO buffer.
    
    Parameters:
        payroll_record (dict): Contains employee details, month, year,
                               basic_salary, allowances, deductions, net_salary, etc.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom Brand Colors
    navy_color = colors.HexColor('#0F172A')
    blue_color = colors.HexColor('#0284C7')
    light_bg = colors.HexColor('#F8FAFC')
    border_color = colors.HexColor('#E2E8F0')
    dark_text = colors.HexColor('#1E293B')
    muted_text = colors.HexColor('#64748B')

    # Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=navy_color,
        alignment=0
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=blue_color,
        alignment=0
    )
    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=muted_text,
        alignment=2
    )
    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=navy_color
    )
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=dark_text
    )
    body_normal = ParagraphStyle(
        'BodyNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=dark_text
    )

    elements = []

    # 1. Header Section (Company Title & Month Information)
    month_name = calendar.month_name[payroll_record['month']]
    period_str = f"{month_name} {payroll_record['year']}"
    gen_date = datetime.now().strftime('%d %B %Y')

    header_data = [
        [
            Paragraph("<b>EMPLOYEE MANAGEMENT SYSTEM</b><br/><font color='#0284C7'>OFFICIAL SALARY SLIP</font>", title_style),
            Paragraph(f"<b>Pay Period:</b> {period_str}<br/><b>Generated On:</b> {gen_date}<br/><b>Slip ID:</b> EMS-PAY-{payroll_record['id']:04d}", meta_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[4.0 * inch, 3.2 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=1.5, color=blue_color, spaceBefore=4, spaceAfter=14))

    # 2. Employee Profile Information Grid
    emp_name = f"{payroll_record['first_name']} {payroll_record['last_name']}"
    status_text = payroll_record.get('status', 'Pending')

    emp_info_data = [
        [
            Paragraph("<b>Employee ID:</b>", body_bold),
            Paragraph(str(payroll_record['employee_code']), body_normal),
            Paragraph("<b>Department:</b>", body_bold),
            Paragraph(str(payroll_record.get('department_name', 'General')), body_normal)
        ],
        [
            Paragraph("<b>Full Name:</b>", body_bold),
            Paragraph(emp_name, body_normal),
            Paragraph("<b>Designation:</b>", body_bold),
            Paragraph(str(payroll_record.get('designation', 'Staff')), body_normal)
        ],
        [
            Paragraph("<b>Official Email:</b>", body_bold),
            Paragraph(str(payroll_record.get('email', 'N/A')), body_normal),
            Paragraph("<b>Payment Status:</b>", body_bold),
            Paragraph(f"<font color='{'#16A34A' if status_text == 'Paid' else '#D97706'}'><b>{status_text}</b></font>", body_normal)
        ],
        [
            Paragraph("<b>Payment Method:</b>", body_bold),
            Paragraph(str(payroll_record.get('payment_method', 'Bank Transfer')), body_normal),
            Paragraph("<b>Payment Date:</b>", body_bold),
            Paragraph(str(payroll_record.get('payment_date') or 'Pending Release'), body_normal)
        ]
    ]
    emp_table = Table(emp_info_data, colWidths=[1.6 * inch, 2.0 * inch, 1.6 * inch, 2.0 * inch])
    emp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('BOX', (0, 0), (-1, -1), 0.5, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(emp_table)
    elements.append(Spacer(1, 16))

    # 3. Earnings & Deductions Breakdown
    elements.append(Paragraph("<b>Salary Structure & Compensation Breakdown</b>", section_title))
    elements.append(Spacer(1, 6))

    basic_val = float(payroll_record['basic_salary'])
    allow_val = float(payroll_record['allowances'])
    deduct_val = float(payroll_record['deductions'])
    net_val = float(payroll_record['net_salary'])

    breakdown_data = [
        [
            Paragraph("<b>EARNINGS</b>", body_bold),
            Paragraph("<b>AMOUNT (INR)</b>", body_bold),
            Paragraph("<b>DEDUCTIONS</b>", body_bold),
            Paragraph("<b>AMOUNT (INR)</b>", body_bold)
        ],
        [
            Paragraph("Basic Salary", body_normal),
            Paragraph(f"₹ {basic_val:,.2f}", body_normal),
            Paragraph("Income Tax / Deductions", body_normal),
            Paragraph(f"₹ {deduct_val:,.2f}", body_normal)
        ],
        [
            Paragraph("Allowances & Bonuses", body_normal),
            Paragraph(f"₹ {allow_val:,.2f}", body_normal),
            Paragraph("Other Statutory Deductions", body_normal),
            Paragraph("₹ 0.00", body_normal)
        ],
        [
            Paragraph("<b>Gross Earnings:</b>", body_bold),
            Paragraph(f"<b>₹ {(basic_val + allow_val):,.2f}</b>", body_bold),
            Paragraph("<b>Total Deductions:</b>", body_bold),
            Paragraph(f"<b>₹ {deduct_val:,.2f}</b>", body_bold)
        ]
    ]

    breakdown_table = Table(breakdown_data, colWidths=[2.1 * inch, 1.5 * inch, 2.1 * inch, 1.5 * inch])
    breakdown_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 0.5, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 3), (-1, 3), light_bg),
    ]))
    elements.append(breakdown_table)
    elements.append(Spacer(1, 16))

    # 4. Net Salary Callout Box
    net_data = [
        [
            Paragraph("<b>NET TAKE-HOME SALARY:</b><br/><font size='8' color='#64748B'>Formula: Basic Salary + Allowances - Deductions</font>", body_bold),
            Paragraph(f"<font size='16' color='#0284C7'><b>₹ {net_val:,.2f}</b></font>", body_bold)
        ]
    ]
    net_table = Table(net_data, colWidths=[4.8 * inch, 2.4 * inch])
    net_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),
        ('BOX', (0, 0), (-1, -1), 1.5, blue_color),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
    ]))
    elements.append(net_table)
    elements.append(Spacer(1, 40))

    # 5. Sign-off and Disclaimer
    sign_data = [
        [
            Paragraph("____________________________<br/><b>Employee Signature</b>", body_normal),
            Paragraph("____________________________<br/><b>Authorized HR Signature</b>", body_normal)
        ]
    ]
    sign_table = Table(sign_data, colWidths=[3.6 * inch, 3.6 * inch])
    sign_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    elements.append(sign_table)
    elements.append(Spacer(1, 20))

    disclaimer = Paragraph(
        "<font size='8' color='#94A3B8'><i>This is an electronically generated salary slip from the Employee Management System. "
        "Any discrepancies should be reported to the Human Resources department within 7 business days.</i></font>",
        ParagraphStyle('Disclaimer', parent=styles['Normal'], alignment=1)
    )
    elements.append(disclaimer)

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
