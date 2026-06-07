from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
from models import db, Student, Result
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
import io

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()

# ── Grade Calculator ──
def get_grade(percentage):
    if percentage >= 90: return "A+", "#2e7d32"
    elif percentage >= 80: return "A",  "#388e3c"
    elif percentage >= 70: return "B",  "#1976d2"
    elif percentage >= 60: return "C",  "#f57c00"
    elif percentage >= 50: return "D",  "#e64a19"
    else: return "F", "#c62828"

# ── Home ──
@app.route('/')
def index():
    search = request.args.get('search', '')
    if search:
        students = Student.query.filter(
            (Student.name.ilike(f'%{search}%')) |
            (Student.roll_no.ilike(f'%{search}%'))
        ).all()
    else:
        students = Student.query.all()
    return render_template('index.html', students=students, search=search)

# ── Add Student ──
@app.route('/add-student', methods=['GET', 'POST'])
def add_student():
    error = None
    if request.method == 'POST':
        name    = request.form['name'].strip()
        roll_no = request.form['roll_no'].strip()
        cls     = request.form['cls'].strip()
        section = request.form['section'].strip()
        existing = Student.query.filter_by(roll_no=roll_no).first()
        if existing:
            error = f"Roll No '{roll_no}' already exists!"
        else:
            student = Student(name=name, roll_no=roll_no, cls=cls, section=section)
            db.session.add(student)
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('add_student.html', error=error)

# ── Add Marks ──
@app.route('/add-marks/<int:student_id>', methods=['GET', 'POST'])
def add_marks(student_id):
    student = Student.query.get_or_404(student_id)
    error = None
    if request.method == 'POST':
        subjects = request.form.getlist('subject')
        marks    = request.form.getlist('marks')
        total    = request.form.getlist('total')
        # Validation
        for s, m, t in zip(subjects, marks, total):
            if int(m) > int(t):
                error = f"❌ '{s}' — Obtained marks ({m}) cannot be greater than Total marks ({t})!"
                return render_template('add_marks.html', student=student, error=error)
            if int(m) < 0 or int(t) <= 0:
                error = f"❌ Marks cannot be negative or zero!"
                return render_template('add_marks.html', student=student, error=error)
        # Delete old marks and save new
        Result.query.filter_by(student_id=student_id).delete()
        for s, m, t in zip(subjects, marks, total):
            result = Result(student_id=student_id, subject=s,
                            marks_obtained=int(m), total_marks=int(t))
            db.session.add(result)
        db.session.commit()
        return redirect(url_for('view_result', student_id=student_id))
    existing = Result.query.filter_by(student_id=student_id).all()
    return render_template('add_marks.html', student=student, error=error, existing=existing)

# ── View Result ──
@app.route('/result/<int:student_id>')
def view_result(student_id):
    student = Student.query.get_or_404(student_id)
    results = Result.query.filter_by(student_id=student_id).all()
    if not results:
        return render_template('result.html', student=student, results=[], no_results=True)
    total_obtained = sum(r.marks_obtained for r in results)
    total_marks    = sum(r.total_marks    for r in results)
    percentage = round((total_obtained / total_marks * 100), 2) if total_marks > 0 else 0
    grade, color = get_grade(percentage)
    status = "PASS" if percentage >= 40 else "FAIL"
    chart_data = {
        'subjects': [r.subject for r in results],
        'obtained': [r.marks_obtained for r in results],
        'total':    [r.total_marks    for r in results]
    }
    return render_template('result.html',
                           student=student, results=results,
                           total_obtained=total_obtained, total_marks=total_marks,
                           percentage=percentage, grade=grade,
                           grade_color=color, status=status,
                           chart_data=chart_data)

# ── Download PDF ──
@app.route('/download-pdf/<int:student_id>')
def download_pdf(student_id):
    student = Student.query.get_or_404(student_id)
    results = Result.query.filter_by(student_id=student_id).all()
    total_obtained = sum(r.marks_obtained for r in results)
    total_marks    = sum(r.total_marks    for r in results)
    percentage = round((total_obtained / total_marks * 100), 2) if total_marks > 0 else 0
    grade, _ = get_grade(percentage)
    status = "PASS" if percentage >= 40 else "FAIL"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=40, leftMargin=40,
                            topMargin=40, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle('title', fontSize=22, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#1a73e8'),
                                  alignment=1, spaceAfter=6)
    elements.append(Paragraph("🎓 Student Result Card", title_style))
    elements.append(Spacer(1, 0.1*inch))

    # Student Info Table
    info_data = [
        ["Name:",    student.name,   "Roll No:", student.roll_no],
        ["Class:",   student.cls,    "Section:", student.section],
    ]
    info_table = Table(info_data, colWidths=[80, 180, 80, 120])
    info_table.setStyle(TableStyle([
        ('FONTNAME',  (0,0), (-1,-1), 'Helvetica'),
        ('FONTNAME',  (0,0), (0,-1),  'Helvetica-Bold'),
        ('FONTNAME',  (2,0), (2,-1),  'Helvetica-Bold'),
        ('FONTSIZE',  (0,0), (-1,-1), 11),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0f4f8')),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.HexColor('#f0f4f8')]),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.2*inch))

    # Marks Table
    marks_data = [["Subject", "Marks Obtained", "Total Marks", "Percentage"]]
    for r in results:
        subj_pct = round(r.marks_obtained / r.total_marks * 100, 1)
        marks_data.append([r.subject, str(r.marks_obtained),
                           str(r.total_marks), f"{subj_pct}%"])
    marks_data.append(["TOTAL", str(total_obtained), str(total_marks), f"{percentage}%"])

    marks_table = Table(marks_data, colWidths=[150, 120, 120, 100])
    marks_table.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  colors.HexColor('#1a73e8')),
        ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
        ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 11),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS',(0,1), (-1,-2), [colors.white, colors.HexColor('#f8f9fa')]),
        ('BACKGROUND',    (0,-1),(-1,-1), colors.HexColor('#e8f0fe')),
        ('FONTNAME',      (0,-1),(-1,-1), 'Helvetica-Bold'),
        ('GRID',          (0,0), (-1,-1), 0.5, colors.HexColor('#dee2e6')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
    ]))
    elements.append(marks_table)
    elements.append(Spacer(1, 0.3*inch))

    # Result Summary
    summary_color = colors.HexColor('#2e7d32') if status == "PASS" else colors.HexColor('#c62828')
    summary_data = [
        ["Grade", "Percentage", "Status"],
        [grade,   f"{percentage}%", status]
    ]
    summary_table = Table(summary_data, colWidths=[160, 160, 160])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  colors.HexColor('#333')),
        ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
        ('FONTNAME',      (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 13),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND',    (0,1), (-1,1),  summary_color),
        ('TEXTCOLOR',     (0,1), (-1,1),  colors.white),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING',    (0,0), (-1,-1), 10),
    ]))
    elements.append(summary_table)

    doc.build(elements)
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=result_{student.roll_no}.pdf'
    return response

# ── Delete Student ──
@app.route('/delete/<int:student_id>')
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    Result.query.filter_by(student_id=student_id).delete()
    db.session.delete(student)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)