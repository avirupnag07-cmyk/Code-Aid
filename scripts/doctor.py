"""Offline, read-only local prerequisites check; never reads .env or prints tool errors."""

import argparse
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def probe(command):
    try:
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def check_version(label, actual, expected, minimum):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", actual or "")
    if not match:
        print("FAIL {}: unavailable".format(label))
        return False
    version = tuple(int(part) for part in match.groups())
    if version < minimum:
        print("FAIL {}: {} is unsupported (pin {})".format(label, actual, expected))
        return False
    if actual.lstrip("v") != expected:
        print("WARN {}: {} installed; reproducible runtime pin is {}".format(label, actual, expected))
    else:
        print("OK   {}: {}".format(label, actual))
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=".venv/bin/python")
    parser.add_argument("--docker", default="docker")
    args = parser.parse_args(argv)
    checks = []
    python_pin = (ROOT / "backend/.python-version").read_text().strip()
    node_pin = (ROOT / "frontend/.nvmrc").read_text().strip()
    python_version = probe([args.python, "-c", "import platform; print(platform.python_version())"])
    checks.append(check_version("Python", python_version, python_pin, (3, 9, 0)))
    node_version = probe(["node", "--version"])
    checks.append(check_version("Node", node_version, node_pin, (20, 0, 0)))
    # Keep the frontend package.json supported upper bound visible too.
    if node_version and re.fullmatch(r"v\d+\.\d+\.\d+", node_version):
        if int(node_version[1:].split(".")[0]) >= 26:
            print("FAIL Node: frontend requires Node <26")
            checks.append(False)
    npm_version = probe(["npm", "--version"])
    npm_ok = bool(re.fullmatch(r"\d+\.\d+\.\d+", npm_version or ""))
    print("OK   npm: {}".format(npm_version) if npm_ok else "FAIL npm: unavailable")
    checks.append(npm_ok)

    # Run metadata inspection in the selected environment, without importing app code.
    dependency_probe = """
import importlib.metadata as metadata
import json
from pathlib import Path
missing = []
for line in Path('backend/requirements.lock').read_text().splitlines():
    if not line.strip() or line.lstrip().startswith('#'):
        continue
    name, expected = line.strip().split('==', 1)
    try:
        installed = metadata.version(name)
    except metadata.PackageNotFoundError:
        installed = None
    if installed != expected:
        missing.append(name)
print(json.dumps(missing))
"""
    dependencies = probe([args.python, "-c", dependency_probe])
    try:
        missing = json.loads(dependencies) if dependencies is not None else None
    except ValueError:
        missing = None
    backend_ok = missing == []
    print("OK   backend dependencies: match requirements.lock" if backend_ok else
          "FAIL backend dependencies: run make setup with the chosen PYTHON_BIN")
    checks.append(backend_ok)
    frontend_ok = probe(["npm", "--prefix", "frontend", "ls", "--depth=0", "--json"]) is not None
    print("OK   frontend dependencies: installed" if frontend_ok else
          "FAIL frontend dependencies: run make setup")
    checks.append(frontend_ok)

    docker_versions = probe([args.docker, "version", "--format", "{{.Client.Version}} {{.Server.Version}}"])
    docker_ok = bool(re.fullmatch(r"[\w.+-]+ [\w.+-]+", docker_versions or ""))
    print("OK   Docker CLI and daemon: {}".format(docker_versions) if docker_ok else
          "FAIL Docker CLI/daemon: install or start Docker, or set DOCKER=/path/to/docker")
    checks.append(docker_ok)
    compose_ok = probe([args.docker, "compose", "version", "--short"]) is not None
    print("OK   Docker Compose: available" if compose_ok else "FAIL Docker Compose: unavailable")
    checks.append(compose_ok)
    print("Doctor passed (runtime pin differences are warnings)." if all(checks) else "Doctor found missing prerequisites.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
