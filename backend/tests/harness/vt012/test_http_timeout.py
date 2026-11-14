"""HTTP loopback thật + Qdrant local thật; server chỉ là fixture giao thức."""

import json
from time import perf_counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Lock, Thread

from qdrant_client import QdrantClient, models

from app.search.qdrant_store import QdrantStore

from .support import config, embedding


def test_t19_real_http_timeout_after_commit_keeps_one_point():
    local = QdrantClient(location=":memory:")
    prepared = QdrantStore(local, collection_name="vt012_http", config=config())
    prepared.ensure_collection()
    release_delayed_response = Event()
    first_write_committed = Event()
    lock = Lock()
    writes = []
    evidence = []
    origin = perf_counter()

    def record(event, **values):
        evidence.append({"elapsed_seconds": round(perf_counter() - origin, 6), "event": event, **values})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, result):
            content = json.dumps({"result": result, "status": "ok", "time": 0.001}).encode()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                # Client đầu tiên đã timeout sau khi server ghi xong.
                pass

        def do_GET(self):
            if self.path.endswith("/exists"):
                self.reply({"exists": True})
            else:
                with lock:
                    info = local.get_collection("vt012_http").model_dump(mode="json")
                self.reply(info)

        def do_PUT(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            with lock:
                points = [models.PointStruct.model_validate(item) for item in body["points"]]
                result = local.upsert("vt012_http", points, wait=True)
                writes.append(body)
                first = len(writes) == 1
                record("SERVER_WRITE_COMMITTED", request=len(writes), point_count=local.count("vt012_http").count, ids=[str(point.id) for point in points])
            if first:
                first_write_committed.set()
                release_delayed_response.wait(timeout=5)
            self.reply(result.model_dump(mode="json"))

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    remote = QdrantClient(
        url=f"http://127.0.0.1:{server.server_port}",
        timeout=0.5,
        check_compatibility=False,
    )
    actual_upsert = remote.upsert

    def observed_upsert(*args, **kwargs):
        try:
            return actual_upsert(*args, **kwargs)
        except Exception as exc:
            source = getattr(exc, "source", exc)
            record("CLIENT_RECEIVED_ERROR", exception=type(exc).__name__, source=type(source).__name__)
            raise

    remote.upsert = observed_upsert
    try:
        store = QdrantStore(
            remote, collection_name="vt012_http", config=config(), retry_delay=0,
        )
        assert store.upsert([embedding("http-after-commit")]) == 1
        assert first_write_committed.is_set()
        assert len(writes) == 2
        assert writes[0] == writes[1]
        assert local.count("vt012_http").count == 1
        record("FINAL_AUDIT", writes=len(writes), point_count=local.count("vt012_http").count, identical_request_bodies=writes[0] == writes[1])
        print("\nHTTP loopback evidence (synthetic server, real REST client and real Qdrant local state):")
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    finally:
        release_delayed_response.set()
        remote.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        local.close()
