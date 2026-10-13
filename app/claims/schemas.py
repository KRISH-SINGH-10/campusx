"""Structured shapes Gemini extracts from the two documents."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal[
    "room_rent",
    "icu",
    "doctor_fees",
    "surgery_ot",
    "nursing",
    "diagnostics",
    "pharmacy",
    "consumables",
    "implants",
    "admin_other",
]


class BillItem(BaseModel):
    description: str
    category: Category
    quantity: float = Field(description="Units or days; 1 if not stated")
    unit_price: float
    amount: float = Field(description="Line total in rupees")


class Bill(BaseModel):
    patient_name: str
    hospital_name: str
    admission_date: str
    discharge_date: str
    diagnosis: str
    procedure: str
    room_type: str
    items: list[BillItem]


class NonPayable(BaseModel):
    keywords: list[str] = Field(description="Lowercase words that identify the item on a bill")
    reason: str
    clause_ref: str


class Sublimit(BaseModel):
    keywords: list[str] = Field(description="Lowercase words that identify the procedure or diagnosis")
    limit_amount: float
    clause_ref: str


class ClauseText(BaseModel):
    ref: str = Field(description="Clause number as printed, e.g. 4.2")
    title: str
    text: str = Field(description="The clause wording, quoted from the policy")


class Policy(BaseModel):
    insurer: str
    policy_name: str
    sum_insured: float
    room_rent_cap_per_day: Optional[float] = None
    room_rent_clause: Optional[str] = None
    icu_cap_per_day: Optional[float] = None
    icu_clause: Optional[str] = None
    proportionate_deduction: bool = False
    proportionate_clause: Optional[str] = None
    copay_percent: float = 0
    copay_clause: Optional[str] = None
    deductible: float = 0
    deductible_clause: Optional[str] = None
    non_payable: list[NonPayable] = []
    sublimits: list[Sublimit] = []
    clauses: list[ClauseText] = []
