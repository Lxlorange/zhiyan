from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PdfReadError


MAX_ATTACHMENT_BYTES = 12 * 1024 * 1024
MAX_EXTRACTED_CHARS = 60000
MAX_RETURNED_TEXT_CHARS = 52000
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".py", ".java", ".ts", ".js", ".html", ".css"}


class AttachmentParseError(ValueError):
    status_code: int = 422

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


class ParsedAttachment(BaseModel):
    filename: str
    content_type: str
    size: int
    parser: str
    text: str = Field(..., min_length=1, max_length=MAX_EXTRACTED_CHARS)
    page_count: Optional[int] = None


async def parse_project_plan_attachment(file: UploadFile) -> ParsedAttachment:
    filename = file.filename or ""
    if not filename:
        raise AttachmentParseError("附件缺少文件名", 400)

    content = await file.read()
    size = len(content)
    if size <= 0:
        raise AttachmentParseError(f"附件为空：{filename}", 400)
    if size > MAX_ATTACHMENT_BYTES:
        raise AttachmentParseError(f"附件过大：{filename}，最大允许 {MAX_ATTACHMENT_BYTES // 1024 // 1024} MB", 413)

    extension = Path(filename).suffix.lower()
    content_type = file.content_type or "application/octet-stream"

    if extension in TEXT_EXTENSIONS:
        text = _decode_text(content, filename)
        return ParsedAttachment(
            filename=filename,
            content_type=content_type,
            size=size,
            parser="text",
            text=_fit_text_size(text, filename),
        )

    if extension == ".pdf" or content_type == "application/pdf":
        text, page_count = _extract_pdf_text(content, filename)
        return ParsedAttachment(
            filename=filename,
            content_type=content_type,
            size=size,
            parser="pdf",
            text=_fit_text_size(text, filename),
            page_count=page_count,
        )

    raise AttachmentParseError(f"不支持的附件类型：{filename}。当前支持 txt/md/csv/json/代码文本和 PDF。", 415)


def _decode_text(content: bytes, filename: str) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise AttachmentParseError(f"无法按 UTF-8 或 GB18030 解码文本附件：{filename}", 422)
    text = text.strip()
    if not text:
        raise AttachmentParseError(f"文本附件未提取到正文：{filename}", 422)
    return text


def _extract_pdf_text(content: bytes, filename: str) -> tuple[str, int]:
    try:
        reader = PdfReader(BytesIO(content))
    except PdfReadError as exc:
        raise AttachmentParseError(f"PDF 解析失败：{filename}，{exc}", 422) from exc
    except Exception as exc:
        raise AttachmentParseError(f"PDF 读取失败：{filename}，{exc}", 422) from exc

    page_texts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:
            raise AttachmentParseError(f"PDF 第 {index} 页文本提取失败：{filename}，{exc}", 422) from exc
        page_text = page_text.strip()
        if page_text:
            page_texts.append(f"[第 {index} 页]\n{page_text}")

    text = "\n\n".join(page_texts).strip()
    if not text:
        raise AttachmentParseError(f"PDF 未提取到可用正文：{filename}。如果是扫描版 PDF，请先 OCR 后上传文本。", 422)
    return text, len(reader.pages)


def _fit_text_size(text: str, filename: str) -> str:
    if len(text) <= MAX_RETURNED_TEXT_CHARS:
        return text

    notice = (
        f"【系统提示】附件 {filename} 原始提取正文 {len(text)} 字，"
        f"已自动节选为 {MAX_RETURNED_TEXT_CHARS} 字以内供项目规划使用；"
        "保留了文档开头和结尾，建议规划时优先参考这些已提取内容。\n\n"
    )
    remaining = MAX_RETURNED_TEXT_CHARS - len(notice)
    if remaining <= 1000:
        raise AttachmentParseError(
            f"附件正文过长：{filename} 提取 {len(text)} 字，当前上限 {MAX_EXTRACTED_CHARS} 字。请拆分资料或上传节选。",
            413,
        )

    head_chars = int(remaining * 0.68)
    tail_chars = remaining - head_chars
    omitted = len(text) - head_chars - tail_chars
    divider = f"\n\n【中间内容已省略 {omitted} 字】\n\n"
    head_chars = max(0, head_chars - len(divider))
    return f"{notice}{text[:head_chars].rstrip()}{divider}{text[-tail_chars:].lstrip()}"
