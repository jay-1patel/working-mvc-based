"""Low-latency inbox notifications used by the admin Chats panel.

The in-process hub is the fast path. The SSE endpoint also fingerprints the
shared database, so multi-worker deployments remain correct without requiring
an additional broker service.
"""

from __future__ import annotations

import queue
import threading
from collections import defaultdict
class InboxEventHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, set[queue.Queue[dict]]] = defaultdict(set)

    def subscribe(self, tenant_id: str) -> queue.Queue[dict]:
        subscriber: queue.Queue[dict] = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers[tenant_id].add(subscriber)
        return subscriber

    def unsubscribe(self, tenant_id: str, subscriber: queue.Queue[dict]) -> None:
        with self._lock:
            subscribers = self._subscribers.get(tenant_id)
            if not subscribers:
                return
            subscribers.discard(subscriber)
            if not subscribers:
                self._subscribers.pop(tenant_id, None)

    def publish(self, tenant_id: str, wa_id: str | None, reason: str) -> None:
        event = {"type": "inbox.updated", "wa_id": wa_id, "reason": reason}
        with self._lock:
            subscribers = list(self._subscribers.get(tenant_id, ()))
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                # A later refresh supersedes stale queued updates.
                try:
                    subscriber.get_nowait()
                    subscriber.put_nowait(event)
                except queue.Empty:
                    pass


inbox_events = InboxEventHub()


def publish_inbox_event(tenant_id: str, wa_id: str | None, reason: str) -> None:
    inbox_events.publish(tenant_id, wa_id, reason)
