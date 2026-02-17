"""Custom JSON encoder for datetime serialization."""
import json
from datetime import datetime
from typing import Any
from fastapi.responses import JSONResponse


class DateTimeJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def json_response_with_datetime(content: Any, status_code: int = 200) -> JSONResponse:
    """Create a JSON response with proper datetime serialization."""
    return JSONResponse(
        content=json.loads(json.dumps(content, cls=DateTimeJSONEncoder)),
        status_code=status_code
    )

