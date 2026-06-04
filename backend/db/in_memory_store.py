from threading import Lock

from backend.models.schemas import ConditionResponse


class ConditionStore:
	def __init__(self) -> None:
		self._lock = Lock()
		self._data: dict[str, ConditionResponse] = {}

	def upsert(self, condition: ConditionResponse) -> None:
		with self._lock:
			self._data[condition.scan_id] = condition

	def get(self, scan_id: str) -> ConditionResponse | None:
		with self._lock:
			return self._data.get(scan_id)


condition_store = ConditionStore()
