from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.entry_tag_vector_service import EntryTagVectorService

router = APIRouter(prefix="/api/entry-tags", tags=["entry-tags"])


@router.post("/sync-vector")
def sync_entry_tags_vector(limit: int = 100, db: Session = Depends(get_db)) -> dict:
    return EntryTagVectorService(db).sync_pending(limit)
