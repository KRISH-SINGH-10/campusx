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
    is_hospital_bill: bool = Field(
        default=True, description="False if the document is not a hospital or medical bill"
    )
    document_kind: str = Field(default="", description="What the document is, in a few words")
    currency: str = Field(default="INR", description="ISO currency code of the amounts, e.g. INR")
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
    is_health_policy: bool = Field(
        default=True,
        description="False if the document is not a health or medical insurance policy "
        "(for example a life, term, motor or travel policy, or an unrelated document)",
    )
    document_kind: str = Field(default="", description="What the document is, in a few words")
    insurer: str
    policy_name: str
    sum_insured: float = Field(description="0 if the document does not state it")
    room_rent_cap_per_day: Optional[float] = None
    room_rent_cap_percent_of_si: Optional[float] = Field(
        default=None, description="Room rent limit per day as a percentage of the sum insured, e.g. 1"
    )
    room_rent_clause: Optional[str] = None
    icu_cap_per_day: Optional[float] = None
    icu_cap_percent_of_si: Optional[float] = Field(
        default=None, description="ICU limit per day as a percentage of the sum insured, e.g. 2"
    )
    icu_clause: Optional[str] = None
    conditional_notes: list[str] = Field(
        default=[],
        description="Limits or co-payments that apply only in some situations (age, zone, a named "
        "illness), one short sentence each with its clause number. At most 5.",
    )
    proportionate_deduction: bool = False
    proportionate_clause: Optional[str] = None
    copay_percent: float = 0
    copay_clause: Optional[str] = None
    deductible: float = 0
    deductible_clause: Optional[str] = None
    non_payable: list[NonPayable] = []
    sublimits: list[Sublimit] = []
    clauses: list[ClauseText] = []
