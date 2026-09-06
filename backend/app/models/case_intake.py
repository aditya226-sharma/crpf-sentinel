"""Crime case dossier models.

A CaseIntake collects raw investigative material for a single registered
FIR/case: photos, the FIR text, call records (CDR), forensic reports, CCTV
video clips and any other supporting documents. ``CaseDocument`` rows point at
the stored file (on the ephemeral uploads disk) so a trilingual PDF report can
be generated from the aggregated evidence.
"""

from sqlalchemy import Column, ForeignKey, Integer, String, Text

from app.database.base import Base, IdMixin, TimestampMixin


class CaseIntake(Base, IdMixin, TimestampMixin):
    __tablename__ = "case_intakes"

    case_id = Column(String(40), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    fir_number = Column(String(60), nullable=True, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    report_language = Column(String(16), nullable=False, default="en")
    created_by = Column(String(32), ForeignKey("users.id"), nullable=True)


class CaseDocument(Base, IdMixin, TimestampMixin):
    __tablename__ = "case_documents"

    case_id = Column(String(32), ForeignKey("case_intakes.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    kind = Column(String(24), nullable=False, default="document", index=True)
    mime = Column(String(120), nullable=False, default="application/octet-stream")
    size = Column(Integer, nullable=False, default=0)
    stored_path = Column(Text, nullable=True)
    uploaded_by = Column(String(32), ForeignKey("users.id"), nullable=True)