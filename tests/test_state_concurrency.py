import os
import time
from multiprocessing import Process, Queue

import pytest

from agents.youtube_researcher import _load_state, _save_state


pytestmark = pytest.mark.slow


def _writer_task(err_q: Queue, path: str, writer_id: int, iterations: int):
    try:
        for i in range(iterations):
            # write a small JSON payload repeatedly to create contention
            _save_state(path, {"writer": writer_id, "i": i})
            # optional small pause to increase interleaving
            time.sleep(0.001)
    except Exception as e:
        # send exception details back to parent
        try:
            err_q.put(f"writer-{writer_id}: {e}")
        except Exception:
            pass


def test_concurrent_state_writes(tmp_path, monkeypatch):
    """Spawn multiple processes that concurrently write the same state file.

    The test asserts:
    - No child writer raised an exception (reported via Queue).
    - Final state file is valid JSON and contains the expected keys.
    """
    tmp_home = str(tmp_path)
    monkeypatch.setenv("HOME", tmp_home)

    state_file = os.path.join(tmp_home, ".swarmagents", "youtube_state.json")
    os.makedirs(os.path.dirname(state_file), exist_ok=True)

    num_procs = 6
    iterations = 200
    err_q: Queue = Queue()
    procs = []

    for wid in range(num_procs):
        p = Process(target=_writer_task, args=(err_q, state_file, wid, iterations))
        p.start()
        procs.append(p)

    # wait for all processes to finish
    for p in procs:
        p.join(timeout=10)
        assert not p.is_alive()

    # collect any errors
    errors = []
    while not err_q.empty():
        try:
            errors.append(err_q.get_nowait())
        except Exception:
            break

    assert not errors, f"Writers reported errors: {errors}"

    # verify final state file is parseable JSON and contains expected keys
    st = _load_state(state_file)
    assert isinstance(st, dict)
    assert "writer" in st and "i" in st
    assert isinstance(st["writer"], int)
    assert isinstance(st["i"], int)
