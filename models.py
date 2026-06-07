from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Student(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String(100), nullable=False)
    roll_no = db.Column(db.String(20),  unique=True, nullable=False)
    cls     = db.Column(db.String(20),  nullable=False)
    section = db.Column(db.String(5),   nullable=False)

class Result(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    student_id     = db.Column(db.Integer, db.ForeignKey('student.id'))
    subject        = db.Column(db.String(50))
    marks_obtained = db.Column(db.Integer)
    total_marks    = db.Column(db.Integer)