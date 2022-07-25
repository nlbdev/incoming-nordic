import threading


class ReadWriteLock():
    """Lock that allows parallel read access.

    Create a lock:

    <code>lock = ReadWriteLock()</code>

    <strong>Get read access:</strong>

    Multiple reads can happen in parallel.

    <pre><code>with lock.read():
        pass</code></pre>
    <br/>

    <strong>Get write access:</strong><br/>

    Will prevent read access while writing,
    and writing are not allowed in parallel.

    <pre><code>with lock.write():
        pass</code></pre>
    <br/>
    """

    _internal_lock = None
    _write_lock = None
    readers = None

    def __init__(self):
        self.internal_lock = threading.Condition()
        self.write_lock = threading.Condition()
        self.readers = 0

    def read(self):
        return ReadWriteLock.ReadLock(self)

    def write(self):
        return ReadWriteLock.WriteLock(self)

    def is_not_reading(self):
        return self.readers == 0

    class ReadLock():  # use ReadWriteLock.read to reference this externally
        parent = None

        def __init__(self, parent):
            self.parent = parent

        def __enter__(self, blocking=True, timeout=-1):
            with self.parent.write_lock:
                with self.parent.internal_lock:
                    self.parent.readers += 1

        def __exit__(self, exception_type, exception_value, traceback):
            with self.parent.internal_lock:
                self.parent.readers -= 1

    class WriteLock():  # use ReadWriteLock.write to reference this externally
        parent = None

        def __init__(self, parent):
            self.parent = parent

        def __enter__(self, blocking=True, timeout=-1):
            with self.parent.write_lock:
                self.parent.write_lock.wait_for(self.parent.is_not_reading)
                return self.parent.write_lock.acquire(blocking, timeout)

        def __exit__(self, exception_type, exception_value, traceback):
            self.parent.write_lock.release()
