from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Priority = Literal["P0", "P1", "P2"]
TestCaseType = Literal["功能测试", "边界测试", "异常测试", "安全测试", "性能测试", "用户体验测试", "兼容性测试"]


class AnalysisArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    summary: str = Field(min_length=1)
    features: list[str] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    boundary_conditions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @field_validator("features", "business_rules", "boundary_conditions", "open_questions")
    @classmethod
    def strip_list_items(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


class GeneratedTestCase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    编号: str = Field(min_length=1)
    标题: str = Field(min_length=1)
    目录: str = Field(default="")
    负责人: str = Field(default="")
    前置条件: list[str] = Field(default_factory=list)
    步骤描述: list[str] = Field(min_length=1)
    预期结果: list[str] = Field(min_length=1)
    优先级: Priority
    类型: TestCaseType
    来源: list[str] = Field(default_factory=list)

    @field_validator("前置条件", "步骤描述", "预期结果", "来源")
    @classmethod
    def normalize_items(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


class GenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    test_cases: list[GeneratedTestCase]
    retrieved_context_count: int = Field(ge=0)


class RetrievedContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    score: float = Field(ge=0.0, le=1.0)
    content_type: Literal["summary", "feature", "business_rule", "boundary_condition"]
    content: str
    metadata: dict[str, str | float | int | bool | None] = Field(default_factory=dict)


class UploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    filename: str
    status: str
    duplicate: bool = False
    message: str


class DocumentRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_type: str
    checksum: str
    status: str
    extraction_error: str | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: int
    analyzed_documents: int
    generated_test_cases: int
    requirement_chunk_vectors: int
    requirement_analysis_vectors: int


class AnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    features: list[str]
    business_rules: list[str]
    boundary_conditions: list[str]
    open_questions: list[str]


class GenerationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_cases: list[GeneratedTestCase]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str


class IngestedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    filename: str
    file_type: str
    checksum: str
    text: str
