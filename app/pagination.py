from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

from app.deps import MAX_INT4


@dataclass
class Pagination:
    limit: int
    offset: int


# Offset pagination: simple, and it allows jumping to any page. Its cost grows with
# the offset (the database reads and discards the skipped rows), which is fine at
# this scale. Keyset (cursor) pagination avoids that at the price of a harder API.
def get_pagination(
    limit: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20,
    # The upper bound only keeps the value inside PostgreSQL's integer range.
    offset: Annotated[int, Query(ge=0, le=MAX_INT4, description="Rows to skip")] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


PageParams = Annotated[Pagination, Depends(get_pagination)]
