from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any]
