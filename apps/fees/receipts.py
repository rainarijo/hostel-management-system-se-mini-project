from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph


def receipt_pdf(payment):
    """Return a PDF receipt for a recorded payment."""
    fee = payment.fee_record
    allocation = fee.allocation
    student = allocation.student
    hostel = allocation.room.hostel

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
        title=f"Fee Receipt {payment.receipt_no}",
    )
    styles = getSampleStyleSheet()

    story = [
        Paragraph("Hostel Management System", styles["Title"]),
        Paragraph("Fee Payment Receipt", styles["Heading2"]),
        Spacer(1, 12),
    ]

    rows = [
        ["Receipt Number", payment.receipt_no],
        ["Student Name", student.name],
        ["Student No.", student.srn],
        ["Hostel", hostel.name],
        ["Room / Bed", f"{allocation.room.room_no} / {allocation.bed_no}"],
        ["Academic Year", allocation.academic_year or fee.academic_year],
        ["Payment Date", payment.paid_on.strftime("%d-%m-%Y")],
        ["Payment Mode", payment.get_mode_display()],
        ["Transaction Reference", payment.txn_reference or "-"],
        ["Amount Paid", f"INR {payment.amount:.2f}"],
        ["Outstanding Balance", f"INR {fee.balance:.2f}"],
    ]

    table = Table(rows, colWidths=[150, 330])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([table, Spacer(1, 18)])
    story.append(
        Paragraph(
            "This receipt confirms that the payment was recorded by the hostel "
            "management system.",
            styles["BodyText"],
        )
    )

    document.build(story)
    return buffer.getvalue()
