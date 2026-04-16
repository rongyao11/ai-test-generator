from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from config import get_settings
from models.schemas import AnalysisArtifact, GeneratedTestCase, KnowledgeBaseStats


class Base(DeclarativeBase):
    pass


class DocumentORM(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AnalysisArtifactORM(Base):
    __tablename__ = "analysis_artifacts"

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    features_json: Mapped[str] = mapped_column(Text, nullable=False)
    business_rules_json: Mapped[str] = mapped_column(Text, nullable=False)
    boundary_conditions_json: Mapped[str] = mapped_column(Text, nullable=False)
    open_questions_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TestCaseORM(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    directory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    preconditions_json: Mapped[str] = mapped_column(Text, nullable=False)
    steps_json: Mapped[str] = mapped_column(Text, nullable=False)
    expected_results_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_refs_json: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _json_dumps(value: Any) -> str:
    import orjson
    return orjson.dumps(value).decode("utf-8")


def _json_loads(value: str) -> Any:
    import orjson
    return orjson.loads(value)


class SQLiteStore:
    def __init__(self) -> None:
        settings = get_settings()
        settings.ensure_data_dirs()
        self.engine = create_engine(settings.sqlite_db_url, future=True)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)
        Base.metadata.create_all(self.engine)
        self._migrate_test_cases()  # add missing columns if any

    def _migrate_test_cases(self) -> None:
        from sqlalchemy import text
        with self.engine.connect() as conn:
            for col, col_type in [("directory", "TEXT"), ("owner", "TEXT"), ("type", "TEXT")]:
                try:
                    conn.execute(text(f'ALTER TABLE test_cases ADD COLUMN {col} {col_type}'))
                    conn.commit()
                except Exception:
                    pass  # column already exists

    @contextmanager
    def session(self) -> Session:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_document_by_checksum(self, checksum: str) -> DocumentORM | None:
        with self.session() as session:
            return session.scalar(select(DocumentORM).where(DocumentORM.checksum == checksum))

    def get_document(self, document_id: str) -> DocumentORM | None:
        with self.session() as session:
            return session.get(DocumentORM, document_id)

    def create_document(
        self,
        document_id: str,
        filename: str,
        file_type: str,
        checksum: str,
        content_text: str,
    ) -> DocumentORM:
        with self.session() as session:
            record = DocumentORM(
                id=document_id,
                filename=filename,
                file_type=file_type,
                checksum=checksum,
                content_text=content_text,
                status="uploaded",
            )
            session.add(record)
            session.flush()
            session.refresh(record)
            return record

    def mark_document_status(self, document_id: str, status: str, extraction_error: str | None = None) -> None:
        with self.session() as session:
            record = session.get(DocumentORM, document_id)
            if record is None:
                return
            record.status = status
            record.extraction_error = extraction_error

    def save_analysis(self, artifact: AnalysisArtifact) -> None:
        with self.session() as session:
            existing = session.get(AnalysisArtifactORM, artifact.document_id)
            payload = {
                "document_id": artifact.document_id,
                "summary": artifact.summary,
                "features_json": _json_dumps(artifact.features),
                "business_rules_json": _json_dumps(artifact.business_rules),
                "boundary_conditions_json": _json_dumps(artifact.boundary_conditions),
                "open_questions_json": _json_dumps(artifact.open_questions),
            }
            if existing is None:
                session.add(AnalysisArtifactORM(**payload))
            else:
                for key, value in payload.items():
                    setattr(existing, key, value)

    def get_analysis(self, document_id: str) -> AnalysisArtifact | None:
        with self.session() as session:
            record = session.get(AnalysisArtifactORM, document_id)
            if record is None:
                return None
            return AnalysisArtifact(
                document_id=record.document_id,
                summary=record.summary,
                features=_json_loads(record.features_json),
                business_rules=_json_loads(record.business_rules_json),
                boundary_conditions=_json_loads(record.boundary_conditions_json),
                open_questions=_json_loads(record.open_questions_json),
            )

    def replace_test_cases(self, document_id: str, cases: list[GeneratedTestCase]) -> None:
        with self.session() as session:
            session.query(TestCaseORM).filter(TestCaseORM.document_id == document_id).delete()
            for case in cases:
                session.add(
                    TestCaseORM(
                        document_id=document_id,
                        case_id=case.编号,
                        title=case.标题,
                        directory=case.目录 or "",
                        owner=case.负责人 or "",
                        priority=case.优先级,
                        preconditions_json=_json_dumps(case.前置条件),
                        steps_json=_json_dumps(case.步骤描述),
                        expected_results_json=_json_dumps(case.预期结果),
                        source_refs_json=_json_dumps(case.来源),
                        type=case.类型 or "",
                    )
                )

    def get_test_cases(self, document_id: str) -> list[GeneratedTestCase]:
        with self.session() as session:
            rows = session.scalars(select(TestCaseORM).where(TestCaseORM.document_id == document_id)).all()
            return [
                GeneratedTestCase(
                    编号=row.case_id,
                    标题=row.title,
                    目录=row.directory or "",
                    负责人=row.owner or "",
                    优先级=row.priority,
                    前置条件=_json_loads(row.preconditions_json),
                    步骤描述=_json_loads(row.steps_json),
                    预期结果=_json_loads(row.expected_results_json),
                    来源=_json_loads(row.source_refs_json),
                    类型=row.type or "功能测试",
                )
                for row in rows
            ]

    def get_stats(self, chunk_count: int, analysis_count: int) -> KnowledgeBaseStats:
        with self.session() as session:
            documents = session.scalar(select(func.count()).select_from(DocumentORM)) or 0
            analyzed_documents = session.scalar(select(func.count()).select_from(AnalysisArtifactORM)) or 0
            generated_test_cases = session.scalar(select(func.count()).select_from(TestCaseORM)) or 0
        return KnowledgeBaseStats(
            documents=documents,
            analyzed_documents=analyzed_documents,
            generated_test_cases=generated_test_cases,
            requirement_chunk_vectors=chunk_count,
            requirement_analysis_vectors=analysis_count,
        )


_sqlite_store: SQLiteStore | None = None


def get_sqlite_store() -> SQLiteStore:
    global _sqlite_store
    if _sqlite_store is None:
        _sqlite_store = SQLiteStore()
    return _sqlite_store
