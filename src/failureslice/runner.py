"""Explicit argv execution. Resource containment is not an OS security sandbox."""
import ctypes
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time
from .jsonio import canonical, exact_keys, integer, loads
from .oracle import Observation, Outcome


class _WindowsJob:
    def __init__(self, process):
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = w.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError("cannot create process job")
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE; breakaway not permitted.
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not self.kernel.AssignProcessToJobObject(self.handle, w.HANDLE(int(process._handle))):
            self.close()
            raise OSError("cannot assign suspended process to job")
        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtResumeProcess.argtypes = [w.HANDLE]
        ntdll.NtResumeProcess.restype = ctypes.c_long
        if ntdll.NtResumeProcess(w.HANDLE(int(process._handle))) != 0:
            self.close()
            raise OSError("cannot resume process")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class CommandRunner:
    def __init__(self, command, cwd, env, environment_identity, code_inputs=(), timeout_ms=5000, max_output=65536):
        if type(command) not in (list, tuple) or not 1 <= len(command) <= 256 or any(type(x) is not str or "\x00" in x or len(x.encode("utf-8")) > 8192 for x in command):
            raise ValueError("command must be a nonempty argv array")
        if command.count("{candidate}") != 1 or any("{candidate}" in x and x != "{candidate}" for x in command):
            raise ValueError("exactly one whole argv element must be {candidate}")
        executable = Path(command[0])
        if not executable.is_absolute() or not executable.is_file():
            raise ValueError("executable must be an existing absolute file")
        if not isinstance(cwd, (str, Path)):
            raise ValueError("cwd must be a path")
        if type(code_inputs) not in (tuple, list) or len(code_inputs) > 128 or any(not isinstance(p, (str, Path)) for p in code_inputs):
            raise ValueError("code_inputs must be a list/tuple of at most 128 file paths")
        self.command = tuple(command)
        self.cwd = Path(cwd).resolve(strict=True)
        if not self.cwd.is_dir():
            raise ValueError("cwd must be a directory")
        if type(env) is not dict or any(type(k) is not str or type(v) is not str or not k or "=" in k or "\x00" in k + v for k, v in env.items()):
            raise ValueError("env must be an explicit string mapping")
        if type(environment_identity) is not dict or not environment_identity:
            raise ValueError("environment_identity must be a nonempty object")
        canonical(environment_identity)
        self.env = dict(env)
        self.environment_identity = environment_identity
        self.code_inputs = tuple(Path(p).resolve(strict=True) for p in code_inputs)
        if any(not p.is_file() for p in self.code_inputs):
            raise ValueError("code_inputs must be files")
        self.timeout_ms = integer(timeout_ms, "timeout_ms", 1, 3_600_000)
        self.max_output = integer(max_output, "max_output", 128, 1_048_576)

    def identity(self):
        # Rehash at each evaluation: changing a script invalidates its observations.
        inputs = (Path(self.command[0]),) + self.code_inputs
        return {"command": list(self.command), "cwd": str(self.cwd), "env": self.env,
                "environment_identity": self.environment_identity, "timeout_ms": self.timeout_ms,
                "max_output": self.max_output, "files": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in inputs]}

    def __call__(self, steps):
        with tempfile.TemporaryDirectory(prefix="failureslice-") as temporary:
            candidate = Path(temporary) / "candidate.json"
            candidate.write_bytes(canonical({"steps": [s.to_dict() for s in steps]}))
            argv = [str(candidate) if x == "{candidate}" else x for x in self.command]
            process = None
            job = None
            overflow = threading.Event()
            buffers = [bytearray(), bytearray()]
            total = [0]
            lock = threading.Lock()
            readers = []
            def collect(stream, index):
                try:
                    while True:
                        chunk = stream.read(4096)
                        if not chunk:
                            break
                        with lock:
                            available = max(0, self.max_output - total[0])
                            buffers[index].extend(chunk[:available])
                            total[0] += len(chunk)
                            if total[0] > self.max_output:
                                overflow.set()
                finally:
                    stream.close()
            def terminate_tree():
                if job:
                    job.close()
                elif process:
                    if os.name == "posix":
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    elif process.poll() is None:
                        process.kill()
            try:
                options = {"creationflags": 0x4} if os.name == "nt" else {"start_new_session": True}
                process = subprocess.Popen(argv, cwd=self.cwd, env=self.env, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, **options)
                if os.name == "nt":
                    job = _WindowsJob(process)
                for index, stream in enumerate((process.stdout, process.stderr)):
                    reader = threading.Thread(target=collect, args=(stream, index), daemon=True)
                    reader.start()
                    readers.append(reader)
                deadline = time.monotonic() + self.timeout_ms / 1000
                category = None
                while process.poll() is None:
                    if overflow.is_set():
                        category = Outcome.ERROR
                        break
                    if time.monotonic() >= deadline:
                        category = Outcome.TIMEOUT
                        break
                    time.sleep(0.005)
                terminate_tree()  # Also close remaining supported descendants after parent success.
                process.wait(timeout=5)
                for reader in readers:
                    reader.join(timeout=5)
                if any(r.is_alive() for r in readers):
                    return Observation(Outcome.ERROR, detail="unsupported detached output descendant")
                if overflow.is_set():
                    return Observation(Outcome.ERROR, detail="output budget exceeded")
                if category:
                    return Observation(category, detail="time budget exceeded")
                try:
                    raw = loads(bytes(buffers[0]))
                    exact_keys(raw, ("status",), ("signature",))
                    status = raw["status"]
                    if status == "PASS" and process.returncode == 0 and "signature" not in raw:
                        return Observation(Outcome.PASS)
                    if status == "INVALID" and process.returncode != 0 and "signature" not in raw:
                        return Observation(Outcome.INVALID)
                    if status == "FAIL" and process.returncode != 0 and type(raw.get("signature")) is dict and raw["signature"]:
                        return Observation(Outcome.OTHER, raw["signature"])
                except ValueError:
                    pass
                return Observation(Outcome.ERROR, detail="invalid oracle protocol or exit status")
            except (OSError, subprocess.SubprocessError, ValueError):
                return Observation(Outcome.ERROR, detail="runner failed")
            finally:
                terminate_tree()
                if process:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
