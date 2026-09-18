from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class LostItemCreate(BaseModel):
    title: str = Field(..., description="Short title of the lost item")
    description: str = Field(..., description="Detailed description of the lost item")
    category: str = Field(..., description="Item category")
    primary_color: str = Field(..., description="Primary color of the item")
    location_name: str = Field(..., description="Name of the location where lost")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate (-90 to 90)")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate (-180 to 180)")
    lost_datetime: str = Field(..., description="Approximate ISO date/time lost")
    hidden_characteristic: str = Field(..., description="Private unique identifying characteristic")
    owner_name: str = Field(..., description="Contact name")
    owner_contact: str = Field(..., description="Phone number or email")
    image_url: Optional[str] = Field(None, description="Image URL or filename")

    @field_validator('lost_datetime')
    @classmethod
    def validate_datetime(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except Exception:
            raise ValueError("lost_datetime must be a valid ISO format datetime string")
        return v

class FoundItemCreate(BaseModel):
    title: str = Field(..., description="Short title of the found item")
    description: str = Field(..., description="Detailed description of the found item")
    category: str = Field(..., description="Item category")
    primary_color: str = Field(..., description="Primary color of the found item")
    location_name: str = Field(..., description="Name of the location where found")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate (-90 to 90)")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate (-180 to 180)")
    found_datetime: str = Field(..., description="Date/time found")
    finder_name: str = Field(..., description="Finder name")
    finder_contact: str = Field(..., description="Finder contact details")
    image_url: Optional[str] = Field(None, description="Image URL or filename")
    public_notes: Optional[str] = Field("", description="Additional public notes")

    @field_validator('found_datetime')
    @classmethod
    def validate_datetime(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except Exception:
            raise ValueError("found_datetime must be a valid ISO format datetime string")
        return v

class WeightConfig(BaseModel):
    image_weight: float = 0.35
    text_weight: float = 0.30
    location_weight: float = 0.15
    time_weight: float = 0.10
    attribute_weight: float = Field(0.10, alias="characteristics_weight")

    @model_validator(mode='before')
    @classmethod
    def check_legacy_alias(cls, values):
        if isinstance(values, dict):
            if "characteristics_weight" in values and "attribute_weight" not in values:
                values["attribute_weight"] = values["characteristics_weight"]
        return values

    class Config:
        populate_by_name = True

class MatchRequest(BaseModel):
    item_id: int = Field(..., description="ID of item to match against candidate pool")
    item_type: str = Field(..., description="'lost' or 'found'")
    weights: Optional[WeightConfig] = None
    min_score_threshold: float = 40.0

class VerifyClaimRequest(BaseModel):
    lost_item_id: int
    found_item_id: int
    claimed_characteristic: str = Field(..., description="Characteristic described by the claimant")

class DocumentContent(BaseModel):
    title: str
    text: str

class ContradictionRequest(BaseModel):
    documents: List[DocumentContent]
