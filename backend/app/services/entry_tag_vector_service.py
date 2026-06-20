from app.db.models import AccountingEntry, EntryTag
from app.services.vector_store_service import safe_vector_store


class EntryTagVectorService:
    def __init__(self, db):
        self.db = db

    def tag_text(self, tag: EntryTag, entry: AccountingEntry | None) -> str:
        return " ".join(
            part
            for part in [
                tag.tag_type,
                tag.tag_value,
                tag.tag_name,
                entry.normalized_text if entry else None,
            ]
            if part
        )

    def point_id(self, tag: EntryTag) -> str:
        return f"entry_tag_{tag.id}"

    def sync_pending(self, limit: int = 100) -> dict:
        store = safe_vector_store()
        pending = (
            self.db.query(EntryTag)
            .filter(EntryTag.vector_pending == True)
            .limit(limit)
            .all()
        )
        if not store:
            return {
                "vector_available": False,
                "synced_count": 0,
                "pending_count": len(pending),
                "message": "向量库当前不可用",
            }

        synced_count = 0
        failed_count = 0
        for tag in pending:
            entry = self.db.get(AccountingEntry, tag.entry_id)
            text = self.tag_text(tag, entry)
            payload = {
                "entry_id": tag.entry_id,
                "tag_id": tag.id,
                "tag_type": tag.tag_type,
                "tag_value": tag.tag_value,
                "tag_name": tag.tag_name,
                "source": "entry_tag",
            }
            try:
                store.upsert_text(self.point_id(tag), text, payload)
                tag.vector_pending = False
                synced_count += 1
            except Exception:
                failed_count += 1
        self.db.commit()
        return {
            "vector_available": True,
            "synced_count": synced_count,
            "pending_count": failed_count,
            "failed_count": failed_count,
        }
