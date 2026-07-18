from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel, Field
from pypdf import PdfReader
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.learning import (
    Course,
    CourseChapter,
    DocumentChunk,
    KnowledgeDocument,
    KnowledgeImportJob,
    KnowledgePoint,
)
from app.models.user import User
from app.schemas import KnowledgeChunkRead, KnowledgeDocumentRead
from app.services.llm_client import LLMResponseError, validate_qwen_config


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".py", ".java", ".ts", ".js", ".html", ".css"}
SUPPORTED_OFFICE_EXTENSIONS = {".pdf", ".pptx", ".ppt", ".docx", ".doc"}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
SUPPORTED_ARCHIVES = {".zip"}
SUPPORTED_EXTENSIONS = SUPPORTED_TEXT_EXTENSIONS | SUPPORTED_OFFICE_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS
MAX_SINGLE_EXTRACTED_CHARS = 1_000_000
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class KnowledgeIngestionError(RuntimeError):
    status_code: int

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


class KnowledgeImportJobRead(BaseModel):
    id: int
    course_code: str
    course_title: str
    source_name: str
    status: str
    total_files: int
    parsed_files: int
    failed_files: int
    total_chunks: int
    error_message: str
    options: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeStorageUsageRead(BaseModel):
    quota_bytes: int
    used_bytes: int
    remaining_bytes: int
    quota_mb: int
    used_mb: float
    remaining_mb: float
    used_percent: float
    document_count: int
    job_count: int


@dataclass
class ParsedSection:
    text: str
    section_title: str = ""
    page_no: Optional[int] = None
    slide_no: Optional[int] = None
    metadata: Optional[dict] = None


@dataclass
class ParsedKnowledgeFile:
    path: Path
    title: str
    doc_type: str
    source_uri: str
    file_hash: str
    sections: list[ParsedSection]
    metadata: dict


def list_import_jobs(db: Session, user: User, limit: int = 20) -> list[KnowledgeImportJobRead]:
    jobs = db.scalars(
        select(KnowledgeImportJob)
        .where(KnowledgeImportJob.user_id == user.id)
        .order_by(KnowledgeImportJob.created_at.desc())
        .limit(limit)
    ).all()
    return [KnowledgeImportJobRead.model_validate(job) for job in jobs]


def get_import_job(db: Session, user: User, job_id: int) -> KnowledgeImportJobRead:
    job = db.get(KnowledgeImportJob, job_id)
    if job is None or job.user_id != user.id:
        raise KnowledgeIngestionError("知识库导入任务不存在", 404)
    return KnowledgeImportJobRead.model_validate(job)


def delete_import_job(db: Session, user: User, job_id: int) -> None:
    job = db.get(KnowledgeImportJob, job_id)
    if job is None or job.user_id != user.id:
        raise KnowledgeIngestionError("知识库导入任务不存在", 404)
    for document in _documents_for_job(db, job_id):
        db.delete(document)
    _delete_job_storage_dir(job.id)
    db.delete(job)
    db.commit()


def get_knowledge_storage_usage(db: Session, user: User) -> KnowledgeStorageUsageRead:
    settings = get_settings()
    quota_bytes = settings.knowledge_storage_quota_mb * 1024 * 1024
    job_ids = db.scalars(select(KnowledgeImportJob.id).where(KnowledgeImportJob.user_id == user.id)).all()
    used_bytes = sum(_job_storage_bytes(job_id) for job_id in job_ids)
    document_count = sum(len(_documents_for_job(db, job_id)) for job_id in job_ids)
    remaining_bytes = max(0, quota_bytes - used_bytes)
    return KnowledgeStorageUsageRead(
        quota_bytes=quota_bytes,
        used_bytes=used_bytes,
        remaining_bytes=remaining_bytes,
        quota_mb=settings.knowledge_storage_quota_mb,
        used_mb=round(used_bytes / 1024 / 1024, 2),
        remaining_mb=round(remaining_bytes / 1024 / 1024, 2),
        used_percent=round(min(100, used_bytes / quota_bytes * 100), 1) if quota_bytes else 0,
        document_count=document_count,
        job_count=len(job_ids),
    )


def list_knowledge_documents(
    db: Session,
    user: User,
    *,
    course_code: Optional[str] = None,
    query: str = "",
    limit: int = 50,
) -> list[KnowledgeDocumentRead]:
    limit = max(1, min(limit, 200))
    statement = (
        select(KnowledgeDocument, func.count(DocumentChunk.id).label("chunk_count"))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == KnowledgeDocument.id)
        .group_by(KnowledgeDocument.id)
        .order_by(KnowledgeDocument.created_at.desc(), KnowledgeDocument.id.desc())
        .limit(limit)
    )
    if course_code:
        statement = statement.where(KnowledgeDocument.course_code == course_code)
    if query:
        like = f"%{query.strip()}%"
        statement = statement.where(
            (KnowledgeDocument.title.ilike(like))
            | (KnowledgeDocument.file_name.ilike(like))
            | (KnowledgeDocument.summary.ilike(like))
            | (KnowledgeDocument.course_code.ilike(like))
        )
    rows = db.execute(statement).all()
    return [
        _document_read(document, chunk_count)
        for document, chunk_count in rows
        if _user_can_manage_document(db, user, document)
    ]


def list_document_chunks(db: Session, user: User, document_id: int, *, limit: int = 100) -> list[KnowledgeChunkRead]:
    document = _get_manageable_document(db, user, document_id)
    limit = max(1, min(limit, 300))
    chunks = db.execute(
        select(DocumentChunk, KnowledgePoint.name)
        .join(KnowledgePoint, KnowledgePoint.id == DocumentChunk.knowledge_point_id, isouter=True)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
        .limit(limit)
    ).all()
    return [
        KnowledgeChunkRead(
            id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            keywords=list(chunk.keywords or []),
            knowledge_point=point_name or "课程资料",
            page_no=chunk.page_no,
            slide_no=chunk.slide_no,
            section_title=chunk.section_title,
            token_count=chunk.token_count,
        )
        for chunk, point_name in chunks
    ]


def delete_knowledge_document(db: Session, user: User, document_id: int) -> None:
    document = _get_manageable_document(db, user, document_id)
    db.delete(document)
    db.commit()


def _document_read(document: KnowledgeDocument, chunk_count: int) -> KnowledgeDocumentRead:
    return KnowledgeDocumentRead(
        id=document.id,
        title=document.title,
        doc_type=document.doc_type,
        source_uri=document.source_uri,
        summary=document.summary,
        file_name=document.file_name,
        file_hash=document.file_hash,
        course_code=document.course_code,
        parse_status=document.parse_status,
        parse_meta=document.parse_meta or {},
        chunk_count=int(chunk_count or 0),
        created_at=document.created_at,
    )


def _get_manageable_document(db: Session, user: User, document_id: int) -> KnowledgeDocument:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise KnowledgeIngestionError("知识库文档不存在", 404)
    if not _user_can_manage_document(db, user, document):
        raise KnowledgeIngestionError("没有权限管理该知识库文档", 403)
    return document


def _user_can_manage_document(db: Session, user: User, document: KnowledgeDocument) -> bool:
    job_id = _job_id_from_document_path(document.file_path)
    if job_id is None:
        return False
    job = db.get(KnowledgeImportJob, job_id)
    return bool(job and job.user_id == user.id)


def _job_id_from_document_path(value: str) -> Optional[int]:
    match = re.search(r"(?:^|[\\/])job-(\d+)(?:[\\/]|$)", value or "")
    if not match:
        return None
    return int(match.group(1))


async def import_knowledge_upload(
    db: Session,
    user: User,
    file: UploadFile,
    *,
    course_code: str,
    course_title: str,
    use_ocr: bool,
    rebuild_course: bool,
) -> KnowledgeImportJobRead:
    if not file.filename:
        raise KnowledgeIngestionError("上传文件缺少文件名", 400)
    settings = get_settings()
    content = await file.read()
    if not content:
        raise KnowledgeIngestionError("上传文件为空", 400)
    max_bytes = settings.knowledge_max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise KnowledgeIngestionError(f"上传文件过大，当前上限 {settings.knowledge_max_upload_mb} MB", 413)
    usage = get_knowledge_storage_usage(db, user)
    if usage.used_bytes + len(content) > usage.quota_bytes:
        remaining_mb = max(0, usage.remaining_bytes / 1024 / 1024)
        raise KnowledgeIngestionError(
            f"知识库空间不足。每位用户可用 {settings.knowledge_storage_quota_mb} MB，"
            f"当前已用 {usage.used_mb} MB，剩余 {remaining_mb:.2f} MB。请删除无用上传记录后再上传。",
            413,
        )

    upload_root = Path(settings.knowledge_upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)

    source_name = _safe_filename(file.filename)
    course_code = _clean_text(course_code)[:64] or "PERSONAL-KNOWLEDGE"
    course_title = _clean_text(course_title)[:255] or "个人知识库"
    job = KnowledgeImportJob(
        user_id=user.id,
        course_code=course_code,
        course_title=course_title,
        source_name=source_name,
        status="running",
        options={"use_ocr": use_ocr, "rebuild_course": rebuild_course, "uploaded_bytes": len(content)},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_dir = upload_root / f"job-{job.id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    source_path = job_dir / source_name
    source_path.write_bytes(content)

    try:
        parsed_files = _parse_upload_source(source_path, job_dir, use_ocr=use_ocr)
        if not parsed_files:
            raise KnowledgeIngestionError("上传资料中没有可解析的课件或文档", 422)

        total_chunks = 0
        job.total_files = len(parsed_files)
        db.commit()
        db.refresh(job)
        for parsed in parsed_files:
            try:
                if rebuild_course and total_chunks == 0 and job.parsed_files == 0 and job.failed_files == 0:
                    _clear_course_imports(db, course_code)
                course = _ensure_course(db, course_code, course_title)
                chapter = _ensure_import_chapter(db, course)
                point_cache = _load_point_cache(db)
                chunks = _persist_parsed_file(db, course, chapter, point_cache, parsed)
                total_chunks += chunks
                job.parsed_files += 1
                db.flush()
                db.commit()
                db.refresh(job)
            except Exception as exc:
                db.rollback()
                job = db.get(KnowledgeImportJob, job.id)
                if job is None:
                    raise KnowledgeIngestionError("知识库导入任务状态丢失，请重新上传", 500) from exc
                job.failed_files += 1
                job.error_message += f"{_clean_text(parsed.path.name)}: {_clean_text(str(exc))}\n"
                db.commit()
                db.refresh(job)
        if job.parsed_files == 0:
            job.total_chunks = 0
            job.status = "failed"
            job.updated_at = datetime.utcnow()
            db.commit()
            raise KnowledgeIngestionError("上传资料已解析，但全部文件入库失败：\n" + (job.error_message or "请检查文件内容和模型 Embedding 配置。"), 422)
        job.total_chunks = total_chunks
        job.status = "completed" if job.failed_files == 0 else "partial_failed"
        job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        return KnowledgeImportJobRead.model_validate(job)
    except Exception as exc:
        db.rollback()
        job = db.get(KnowledgeImportJob, job.id)
        if job is None:
            raise KnowledgeIngestionError(f"知识库导入失败：{_clean_text(str(exc))}", 500) from exc
        job.status = "failed"
        job.error_message = _clean_text(str(exc))
        job.updated_at = datetime.utcnow()
        db.commit()
        if isinstance(exc, KnowledgeIngestionError):
            raise
        raise KnowledgeIngestionError(f"知识库导入失败：{exc}", 500) from exc


def rebuild_missing_embeddings(db: Session, limit: int = 200) -> int:
    rows = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.embedding.is_(None))
        .order_by(DocumentChunk.id)
        .limit(limit)
    ).all()
    for chunk in rows:
        chunk.embedding = embed_text(chunk.content)
    db.commit()
    return len(rows)


def _parse_upload_source(source_path: Path, job_dir: Path, *, use_ocr: bool) -> list[ParsedKnowledgeFile]:
    extension = source_path.suffix.lower()
    candidates: list[Path] = []
    if extension in SUPPORTED_ARCHIVES:
        extract_dir = job_dir / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        _extract_zip(source_path, extract_dir)
        candidates = [path for path in extract_dir.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS]
    elif extension in SUPPORTED_EXTENSIONS:
        candidates = [source_path]
    else:
        raise KnowledgeIngestionError(f"不支持的上传格式：{source_path.name}", 415)

    parsed: list[ParsedKnowledgeFile] = []
    errors: list[str] = []
    for candidate in candidates:
        try:
            parsed.append(_parse_single_file(candidate, use_ocr=use_ocr))
        except Exception as exc:
            errors.append(f"{candidate.name}: {exc}")
    if not parsed and errors:
        raise KnowledgeIngestionError("所有文件解析失败：\n" + "\n".join(errors[:20]), 422)
    return parsed


def _extract_zip(source_path: Path, extract_dir: Path) -> None:
    try:
        with zipfile.ZipFile(source_path) as archive:
            for member in archive.infolist():
                member_path = Path(_clean_zip_member_name(member.filename))
                if member.is_dir():
                    continue
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise KnowledgeIngestionError(f"ZIP 包含不安全路径：{member.filename}", 400)
                target = extract_dir / member_path
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except zipfile.BadZipFile as exc:
        raise KnowledgeIngestionError(f"ZIP 文件损坏或格式不正确：{source_path.name}", 422) from exc


def _clean_zip_member_name(filename: str) -> str:
    parts = [_safe_filename(part) for part in Path(filename).parts if part not in {"", ".", ".."}]
    if not parts:
        return "upload.bin"
    return str(Path(*parts))


def _parse_single_file(path: Path, *, use_ocr: bool) -> ParsedKnowledgeFile:
    extension = path.suffix.lower()
    if extension == ".ppt":
        path = _convert_legacy_office(path, ".pptx")
        extension = path.suffix.lower()
    if extension == ".doc":
        path = _convert_legacy_office(path, ".docx")
        extension = path.suffix.lower()

    if extension == ".pdf":
        sections = _parse_pdf(path, use_ocr=use_ocr)
    elif extension == ".pptx":
        sections = _parse_pptx(path)
    elif extension == ".docx":
        sections = _parse_docx(path)
    elif extension in SUPPORTED_TEXT_EXTENSIONS:
        sections = _parse_text(path)
    elif extension in SUPPORTED_IMAGE_EXTENSIONS:
        sections = _parse_image(path, use_ocr=use_ocr)
    else:
        raise KnowledgeIngestionError(f"不支持的课件类型：{path.name}", 415)

    text_len = sum(len(section.text) for section in sections)
    if text_len <= 0:
        raise KnowledgeIngestionError(f"未提取到可用正文：{path.name}", 422)
    if text_len > MAX_SINGLE_EXTRACTED_CHARS:
        raise KnowledgeIngestionError(f"单个文件正文过长：{path.name}，请拆分后导入", 413)
    return ParsedKnowledgeFile(
        path=path,
        title=_clean_text(path.stem)[:255] or "导入资料",
        doc_type=extension.removeprefix("."),
        source_uri=_clean_text(str(path)),
        file_hash=_sha256_file(path),
        sections=sections,
        metadata={"extension": extension, "text_chars": text_len},
    )

def _parse_pdf(path: Path, *, use_ocr: bool) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    reader = PdfReader(str(path))
    for page_index, page in enumerate(reader.pages, start=1):
        text_value = _normalize_text(page.extract_text() or "")
        if text_value:
            sections.append(ParsedSection(text=text_value, page_no=page_index, section_title=f"第 {page_index} 页"))
    if not sections and use_ocr:
        sections = _ocr_pdf_or_image(path)
    if not sections:
        raise KnowledgeIngestionError(f"PDF 未提取到文本：{path.name}。如为扫描版，请启用 OCR 并安装本地 OCR。", 422)
    return sections


def _parse_pptx(path: Path) -> list[ParsedSection]:
    from pptx import Presentation

    presentation = Presentation(str(path))
    sections: list[ParsedSection] = []
    for slide_index, slide in enumerate(presentation.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text:
                parts.append(_clean_text(shape.text))
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    parts.append(" | ".join(_clean_text(cell.text) for cell in row.cells if cell.text))
        notes = ""
        try:
            notes = slide.notes_slide.notes_text_frame.text
        except Exception:
            notes = ""
        if notes:
            parts.append("备注：" + _clean_text(notes))
        text_value = _normalize_text("\n".join(part.strip() for part in parts if part and part.strip()))
        if text_value:
            sections.append(ParsedSection(text=text_value, slide_no=slide_index, section_title=f"第 {slide_index} 页幻灯片"))
    if not sections:
        raise KnowledgeIngestionError(f"PPTX 未提取到文本：{path.name}", 422)
    return sections


def _parse_docx(path: Path) -> list[ParsedSection]:
    from docx import Document

    document = Document(str(path))
    sections: list[ParsedSection] = []
    current_title = ""
    buffer: list[str] = []
    for paragraph in document.paragraphs:
        value = _normalize_text(paragraph.text)
        if not value:
            continue
        style_name = paragraph.style.name if paragraph.style else ""
        if style_name.lower().startswith("heading") and buffer:
            sections.append(ParsedSection(text="\n".join(buffer), section_title=current_title))
            buffer = []
            current_title = value
        else:
            buffer.append(value)
    table_text = []
    for table in document.tables:
        for row in table.rows:
            row_text = " | ".join(_clean_text(cell.text).strip() for cell in row.cells if _clean_text(cell.text).strip())
            if row_text:
                table_text.append(row_text)
    buffer.extend(table_text)
    if buffer:
        sections.append(ParsedSection(text="\n".join(buffer), section_title=current_title))
    if not sections:
        raise KnowledgeIngestionError(f"DOCX 未提取到文本：{path.name}", 422)
    return sections


def _parse_text(path: Path) -> list[ParsedSection]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text_value = _normalize_text(raw.decode(encoding))
            break
        except UnicodeDecodeError:
            continue
    else:
        raise KnowledgeIngestionError(f"文本文件无法按 UTF-8 或 GB18030 解码：{path.name}", 422)
    if not text_value:
        raise KnowledgeIngestionError(f"文本文件为空：{path.name}", 422)
    return [ParsedSection(text=text_value, section_title=path.name)]


def _parse_image(path: Path, *, use_ocr: bool) -> list[ParsedSection]:
    if not use_ocr:
        raise KnowledgeIngestionError(f"图片文件需要启用 OCR 后才能导入：{path.name}", 422)
    return _ocr_pdf_or_image(path)


def _ocr_pdf_or_image(path: Path) -> list[ParsedSection]:
    settings = get_settings()
    if settings.local_ocr_engine.lower() != "tesseract":
        raise KnowledgeIngestionError(f"未支持的本地 OCR 引擎：{settings.local_ocr_engine}", 501)
    pytesseract, Image = _load_ocr_dependencies()
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    if path.suffix.lower() == ".pdf":
        return _ocr_pdf(path, pytesseract)
    text_value = _normalize_text(pytesseract.image_to_string(Image.open(path), lang="chi_sim+eng"))
    if not text_value:
        raise KnowledgeIngestionError(f"OCR 未识别到文字：{path.name}", 422)
    return [ParsedSection(text=text_value, section_title=path.name, metadata={"ocr": True})]


def _load_ocr_dependencies():
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise KnowledgeIngestionError("缺少 OCR 依赖，请安装 pytesseract 和 Pillow", 500) from exc
    return pytesseract, Image


def _ocr_pdf(path: Path, pytesseract) -> list[ParsedSection]:
    try:
        import fitz
    except ImportError as exc:
        raise KnowledgeIngestionError("扫描版 PDF OCR 缺少 PyMuPDF，请安装 backend/requirements.txt 后重试。", 500) from exc

    sections: list[ParsedSection] = []
    try:
        with fitz.open(str(path)) as document:
            for page_index, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image_bytes = pixmap.tobytes("png")
                text_value = _normalize_text(
                    pytesseract.image_to_string(_image_from_bytes(image_bytes), lang="chi_sim+eng")
                )
                if text_value:
                    sections.append(
                        ParsedSection(
                            text=text_value,
                            page_no=page_index,
                            section_title=f"第 {page_index} 页 OCR",
                            metadata={"ocr": True},
                        )
                    )
    except KnowledgeIngestionError:
        raise
    except Exception as exc:
        raise KnowledgeIngestionError(f"PDF OCR 失败：{path.name}，{_clean_text(str(exc))}", 422) from exc
    if not sections:
        raise KnowledgeIngestionError(f"OCR 未识别到文字：{path.name}", 422)
    return sections


def _image_from_bytes(image_bytes: bytes):
    from PIL import Image

    return Image.open(io.BytesIO(image_bytes))


def _convert_legacy_office(path: Path, target_suffix: str) -> Path:
    settings = get_settings()
    libreoffice = settings.libreoffice_path.strip() or shutil.which("soffice") or shutil.which("libreoffice")
    if not libreoffice:
        raise KnowledgeIngestionError(f"{path.suffix} 旧格式需要安装 LibreOffice 后转换：{path.name}", 501)
    libreoffice_path = Path(libreoffice)
    if not libreoffice_path.exists():
        raise KnowledgeIngestionError(f"LIBREOFFICE_PATH 指向的文件不存在：{libreoffice}", 501)
    output_dir = path.parent / "converted"
    output_dir.mkdir(exist_ok=True)
    cmd = [str(libreoffice_path), "--headless", "--convert-to", target_suffix.removeprefix("."), "--outdir", str(output_dir), str(path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
    if result.returncode != 0:
        raise KnowledgeIngestionError(f"LibreOffice 转换失败：{path.name}，{result.stderr or result.stdout}", 422)
    converted = output_dir / f"{path.stem}{target_suffix}"
    if not converted.exists():
        raise KnowledgeIngestionError(f"LibreOffice 转换后未找到目标文件：{converted.name}", 422)
    return converted


def _ensure_course(db: Session, code: str, title: str) -> Course:
    course = db.scalar(select(Course).where(Course.code == code))
    if course is None:
        course = Course(code=code, title=title, description=f"{title} 课程知识库")
        db.add(course)
        db.flush()
    else:
        course.title = title
    return course


def _ensure_import_chapter(db: Session, course: Course) -> CourseChapter:
    chapter = db.scalar(
        select(CourseChapter).where(CourseChapter.course_id == course.id, CourseChapter.order_index == 999)
    )
    if chapter is None:
        chapter = CourseChapter(course_id=course.id, order_index=999, title="导入课件资料", summary="由教师课件、习题和解析自动导入的资料。")
        db.add(chapter)
        db.flush()
    return chapter


def _load_point_cache(db: Session) -> dict[str, KnowledgePoint]:
    return {point.name: point for point in db.scalars(select(KnowledgePoint)).all()}


def _clear_course_imports(db: Session, course_code: str) -> None:
    docs = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.course_code == course_code)).all()
    for document in docs:
        db.delete(document)
    db.flush()


def _persist_parsed_file(
    db: Session,
    course: Course,
    chapter: CourseChapter,
    point_cache: dict[str, KnowledgePoint],
    parsed: ParsedKnowledgeFile,
) -> int:
    existing = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.file_hash == parsed.file_hash))
    title = _clean_text(parsed.title)[:255] or "导入资料"
    source_uri = _clean_text(parsed.source_uri)
    file_path = _clean_text(str(parsed.path))
    file_name = _safe_filename(parsed.path.name)
    summary = _summarize_sections(parsed.sections)
    parse_meta = _clean_metadata(parsed.metadata)
    if existing is not None:
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == existing.id))
        document = existing
        document.course_id = course.id
        document.title = title
        document.doc_type = parsed.doc_type
        document.source_uri = source_uri
        document.summary = summary
        document.file_path = file_path
        document.file_name = file_name
        document.course_code = course.code
        document.parse_status = "ready"
        document.parse_meta = parse_meta
    else:
        document = KnowledgeDocument(
            course_id=course.id,
            title=title,
            doc_type=parsed.doc_type,
            source_uri=source_uri,
            summary=summary,
            file_path=file_path,
            file_name=file_name,
            file_hash=parsed.file_hash,
            course_code=course.code,
            parse_status="ready",
            parse_meta=parse_meta,
        )
        db.add(document)
        db.flush()

    chunks = list(_chunk_sections(parsed.sections))
    for index, section in enumerate(chunks, start=1):
        point_name = _infer_point_name(title, section.text)
        point = _ensure_point(db, chapter, point_cache, point_name, section.text)
        safe_content = _clean_text(section.text)
        db.add(
            DocumentChunk(
                document_id=document.id,
                knowledge_point_id=point.id,
                chunk_index=index,
                content=safe_content,
                keywords=_extract_keywords(title, section.text),
                page_no=section.page_no,
                slide_no=section.slide_no,
                section_title=_clean_text(section.section_title)[:255],
                token_count=len(safe_content),
                embedding=embed_text(safe_content),
                retrieval_weight=1.0,
                extra_meta=_clean_metadata(section.metadata or {}),
            )
        )
    db.flush()
    return len(chunks)


def _ensure_point(
    db: Session,
    chapter: CourseChapter,
    point_cache: dict[str, KnowledgePoint],
    name: str,
    text_value: str,
) -> KnowledgePoint:
    safe_name = _clean_text(name)[:128] or "导入知识点"
    point = point_cache.get(safe_name)
    if point is None:
        safe_description = _clean_text(text_value)[:300]
        point = KnowledgePoint(
            chapter_id=chapter.id,
            name=safe_name,
            description=safe_description,
            prerequisites=[],
            tags=["imported", "courseware"],
            difficulty="medium",
        )
        db.add(point)
        db.flush()
        point_cache[safe_name] = point
    return point


def _chunk_sections(sections: list[ParsedSection]) -> list[ParsedSection]:
    settings = get_settings()
    size = max(400, settings.knowledge_chunk_chars)
    overlap = max(0, min(settings.knowledge_chunk_overlap, size // 2))
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise KnowledgeIngestionError("缺少 RAG 文档切分依赖 langchain-text-splitters，请安装 backend/requirements.txt。", 500) from exc

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", "。", "！", "？", ";", "；", " ", ""],
    )
    chunks: list[ParsedSection] = []
    for section in sections:
        text_value = _normalize_text(section.text)
        for part_index, part in enumerate(splitter.split_text(text_value), start=1):
            part = _normalize_text(part)
            if not part:
                continue
            section_title = section.section_title if len(text_value) <= size else f"{section.section_title} #{part_index}".strip()
            chunks.append(
                ParsedSection(
                    text=part,
                    section_title=section_title,
                    page_no=section.page_no,
                    slide_no=section.slide_no,
                    metadata=section.metadata,
                )
            )
    return chunks


def search_knowledge_enhanced(db: Session, query: str, limit: int = 8) -> list[dict]:
    vector = embed_text(query)
    terms = [term.strip() for term in query.replace("，", " ").replace("、", " ").replace("/", " ").split() if term.strip()]
    keyword_filters = " OR ".join(
        [
            "dc.content ILIKE :pattern",
            "kp.name ILIKE :pattern",
            "kd.title ILIKE :pattern",
            "kd.summary ILIKE :pattern",
        ]
    )
    pattern = f"%{terms[0] if terms else query}%"
    sql = text(
        f"""
        SELECT
            dc.id AS chunk_id,
            kd.title AS document_title,
            kd.doc_type AS document_type,
            COALESCE(kp.name, '课程资料') AS knowledge_point,
            dc.content AS content,
            kd.source_uri AS source_uri,
            dc.keywords AS keywords,
            dc.page_no AS page_no,
            dc.slide_no AS slide_no,
            dc.section_title AS section_title,
            CASE WHEN dc.embedding IS NULL THEN NULL ELSE dc.embedding <=> CAST(:embedding AS vector) END AS distance,
            CASE WHEN ({keyword_filters}) THEN 1 ELSE 0 END AS keyword_hit
        FROM document_chunks dc
        JOIN knowledge_documents kd ON dc.document_id = kd.id
        LEFT JOIN knowledge_points kp ON dc.knowledge_point_id = kp.id
        ORDER BY
            keyword_hit DESC,
            CASE WHEN dc.embedding IS NULL THEN 1 ELSE 0 END ASC,
            distance ASC NULLS LAST,
            dc.retrieval_weight DESC,
            dc.id DESC
        LIMIT :limit
        """
    )
    rows = db.execute(sql, {"embedding": _vector_literal(vector), "pattern": pattern, "limit": limit}).mappings().all()
    return [dict(row) for row in rows]


def build_rag_context(db: Session, query: str, limit: int = 8) -> str:
    hits = search_knowledge_enhanced(db, query, limit=limit)
    if not hits:
        return "未检索到课程知识库资料。请要求用户补充课件、论文或实验资料。"
    lines = []
    for index, hit in enumerate(hits, start=1):
        loc = []
        if hit.get("page_no"):
            loc.append(f"页码 {hit['page_no']}")
        if hit.get("slide_no"):
            loc.append(f"幻灯片 {hit['slide_no']}")
        location = f"（{'，'.join(loc)}）" if loc else ""
        lines.append(
            f"[{index}] {hit['knowledge_point']} / {hit['document_title']}{location} / {hit['document_type']}\n"
            f"source={hit['source_uri']}\n"
            f"{hit['content'][:1200]}"
        )
    return "\n\n".join(lines)


def embed_text(text_value: str) -> list[float]:
    settings = get_settings()
    if settings.knowledge_embedding_provider.lower() != "qwen":
        raise KnowledgeIngestionError(f"不支持的 embedding provider：{settings.knowledge_embedding_provider}", 501)
    validate_qwen_config()
    import urllib.request
    import urllib.error

    payload = {
        "model": settings.knowledge_embedding_model,
        "input": text_value[:8192],
        "encoding_format": "float",
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.qwen_base_url.rstrip('/')}/embeddings",
        data=data,
        headers={
            "Authorization": f"Bearer {settings.qwen_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.qwen_timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise LLMResponseError(f"千问 Embedding 接口返回错误：{exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMResponseError(f"无法连接千问 Embedding 接口：{exc.reason}") from exc
    try:
        vector = body["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMResponseError("千问 Embedding 响应缺少 data[0].embedding") from exc
    if len(vector) != settings.knowledge_embedding_dim:
        raise LLMResponseError(f"Embedding 维度不匹配：返回 {len(vector)}，配置 {settings.knowledge_embedding_dim}")
    return vector


def _infer_point_name(title: str, text_value: str) -> str:
    candidates = [line.strip("# ：:") for line in text_value.splitlines() if line.strip()]
    if candidates:
        candidate = candidates[0]
        if 2 <= len(candidate) <= 40:
            return candidate[:128]
    return title[:128] or "导入知识点"


def _extract_keywords(title: str, text_value: str) -> list[str]:
    raw = f"{title} {text_value[:500]}"
    terms = []
    for term in raw.replace("，", " ").replace("。", " ").replace("、", " ").replace("/", " ").split():
        cleaned = term.strip(" ：:;；,.，。()[]【】")
        if 2 <= len(cleaned) <= 24 and cleaned not in terms:
            terms.append(cleaned)
        if len(terms) >= 12:
            break
    return terms


def _summarize_sections(sections: list[ParsedSection]) -> str:
    text_value = "\n".join(section.text for section in sections)
    return _normalize_text(text_value)[:1000]


def _normalize_text(text_value: str) -> str:
    cleaned = _clean_text(text_value)
    return "\n".join(line.strip() for line in cleaned.splitlines() if line.strip())


def _clean_text(value: object) -> str:
    text_value = "" if value is None else str(value)
    text_value = text_value.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    text_value = CONTROL_CHARS_RE.sub("", text_value)
    return text_value.strip()


def _clean_metadata(value: object) -> object:
    if isinstance(value, dict):
        return {_clean_text(key): _clean_metadata(item) for key, item in value.items() if _clean_text(key)}
    if isinstance(value, list):
        return [_clean_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [_clean_metadata(item) for item in value]
    if isinstance(value, str):
        return _clean_text(value)
    return value


def _safe_filename(filename: str) -> str:
    recovered = _recover_zip_mojibake(filename)
    value = _clean_text(Path(recovered).name)
    return value or "upload.bin"


def _recover_zip_mojibake(value: str) -> str:
    text_value = _clean_text(value)
    if not text_value:
        return text_value
    try:
        recovered = text_value.encode("cp437").decode("gb18030")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text_value
    return recovered if any("\u4e00" <= char <= "\u9fff" for char in recovered) else text_value


def _job_storage_dir(job_id: int) -> Path:
    return Path(get_settings().knowledge_upload_dir) / f"job-{job_id}"


def _job_storage_bytes(job_id: int) -> int:
    job_dir = _job_storage_dir(job_id)
    if not job_dir.exists():
        return 0
    return sum(path.stat().st_size for path in job_dir.rglob("*") if path.is_file())


def _documents_for_job(db: Session, job_id: int) -> list[KnowledgeDocument]:
    documents = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.file_path.ilike("%job-%"))).all()
    return [document for document in documents if _job_id_from_document_path(document.file_path) == job_id]


def _delete_job_storage_dir(job_id: int) -> None:
    job_dir = _job_storage_dir(job_id)
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in vector) + "]"
