#!/usr/bin/env python3
"""The simulation image: build it, name it, and run things in it.

    python tools/sim_image.py build     build the image this tree describes (minutes the first time)
    python tools/sim_image.py tag       print its name
    python tools/sim_image.py check     the `rtl-image` check, by hand
    --root DIR                          another copy of the tree

THE IMAGE'S NAME IS MADE FROM THE FILES IT IS BUILT FROM. Its tag is the first
sixteen hex digits of a SHA-256 over docker/Dockerfile.sim and
docker/requirements-sim.txt (each as its name, a zero byte, and its bytes with
CR LF read as LF). So an image built from other files has another name, and a
tree whose docker files changed since the last build finds no image at all:
that is refused as IMAGE-MISSING, never run on the stale one. The image also
carries the whole hash as the label `undertone.inputs`, and a tag whose label
disagrees is refused as IMAGE-LABEL.

What this cannot see: whether the image under that name was built by this
tool. Anyone can tag any image `undertone-sim:<hash>` and label it. And the
base image's own packages are whatever its archive served on the day of the
build; `versions()` reads what the image holds, and the `rtl-image` stage
prints it.

Everything here that talks to Docker goes through `docker()`, which runs the
`docker` on the PATH with a list of arguments and no shell.
"""
import hashlib
import os
import subprocess
import sys

REPOSITORY = "undertone-sim"
INPUTS = ("docker/Dockerfile.sim", "docker/requirements-sim.txt")
LABEL = "undertone.inputs"


class ImageRefusal(Exception):
    """Something about Docker or the image makes the question unanswerable. `name` is the refusal's name."""

    def __init__(self, name, detail):
        super().__init__("%s: %s" % (name, detail))
        self.name = name


def inputs_hash(root):
    h = hashlib.sha256()
    for rel in INPUTS:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            raise ImageRefusal("IMAGE-INPUT-MISSING", "%s is not in the tree" % rel)
        with open(path, "rb") as f:
            h.update(rel.encode("ascii") + b"\x00" + f.read().replace(b"\r\n", b"\n") + b"\x00")
    return h.hexdigest()


def tag(root):
    return "%s:%s" % (REPOSITORY, inputs_hash(root)[:16])


def docker(args, timeout=1800, **kw):
    try:
        return subprocess.run(["docker"] + list(args), capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace", **kw)
    except FileNotFoundError:
        raise ImageRefusal("DOCKER-MISSING", "there is no `docker` on the PATH")
    except subprocess.TimeoutExpired:
        raise ImageRefusal("DOCKER-TIMEOUT", "`docker %s` ran past %d seconds" % (" ".join(args[:2]), timeout))


def require(root):
    """The name of the image this tree describes, or a refusal by name."""
    name, want = tag(root), inputs_hash(root)
    r = docker(["image", "inspect", "--format", "{{index .Config.Labels \"%s\"}}" % LABEL, name], timeout=60)
    if r.returncode != 0:
        if "No such image" in r.stderr or "no such image" in r.stderr.lower():
            raise ImageRefusal("IMAGE-MISSING", "no image %s; this tree's docker files have no build on this machine. "
                               "Run: python tools/sim_image.py build" % name)
        raise ImageRefusal("DOCKER-UNREACHABLE", (r.stderr.strip().splitlines() or ["docker image inspect failed"])[-1])
    if r.stdout.strip() != want:
        raise ImageRefusal("IMAGE-LABEL", "%s carries the label %r, not this tree's %s" % (name, r.stdout.strip(), want))
    return name


def run(root, mounts, command, timeout=1800):
    """Run a command in the image. `mounts` is [(host folder, container path, "ro" | "rw")]."""
    name = require(root)
    args = ["run", "--rm", "--network", "none"]
    for host, inside, mode in mounts:
        args += ["-v", "%s:%s%s" % (os.path.abspath(host).replace("\\", "/"), inside, ":ro" if mode == "ro" else "")]
    return docker(args + [name] + list(command), timeout=timeout)


def versions(root):
    """What the image holds: {"pip": {name: version}, "iverilog": ..., "python": ..., "gcc": ...}."""
    r = run(root, [], ["sh", "-c", "pip freeze && echo ---- && dpkg-query -W -f '${Version}\\n' iverilog "
                                   "&& python --version && gcc -dumpfullversion"], timeout=120)
    if r.returncode != 0:
        raise ImageRefusal("IMAGE-BROKEN", "reading the image's versions failed: %s" % r.stderr.strip()[-300:])
    freeze, rest = r.stdout.split("----\n")
    pip = {}
    for line in freeze.split("\n"):
        if "==" in line:
            n, v = line.strip().split("==", 1)
            pip[n.lower()] = v
    rest = [x.strip() for x in rest.strip().split("\n")]
    return {"pip": pip, "iverilog": rest[0], "python": rest[1].replace("Python ", ""), "gcc": rest[2]}


def pins(root):
    """What the tree's docker files pin: {"pip": {name: version}, "iverilog": version}."""
    pip = {}
    with open(os.path.join(root, INPUTS[1]), encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line:
                if "==" not in line:
                    raise ImageRefusal("IMAGE-INPUT-MALFORMED", "%s has a line that pins nothing: %r" % (INPUTS[1], line))
                n, v = line.split("==", 1)
                pip[n.strip().lower()] = v.strip()
    iverilog = None
    with open(os.path.join(root, INPUTS[0]), encoding="utf-8") as f:
        for line in f:
            if line.startswith("ARG IVERILOG_VERSION="):
                iverilog = line.split("=", 1)[1].strip()
    if iverilog is None:
        raise ImageRefusal("IMAGE-INPUT-MALFORMED", "%s has no line ARG IVERILOG_VERSION=" % INPUTS[0])
    return {"pip": pip, "iverilog": iverilog}


def build(root):
    name, digest = tag(root), inputs_hash(root)
    r = subprocess.run(["docker", "build", "-t", name, "--label", "%s=%s" % (LABEL, digest),
                        "-f", os.path.join(root, INPUTS[0]), os.path.join(root, "docker")])
    if r.returncode != 0:
        print("REFUSED IMAGE-BUILD-FAILED: docker build exited %d" % r.returncode)
        return 2
    print("built %s" % name)
    return 0


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if "--root" in argv:
        root = os.path.abspath(argv[argv.index("--root") + 1])
    what = argv[0] if argv else ""
    try:
        if what == "build":
            return build(root)
        if what == "tag":
            print(tag(root))
            return 0
        if what == "check":
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import check_rtl
            return check_rtl.run("rtl-image", root, None)[0]
    except ImageRefusal as e:
        print("REFUSED %s" % e)
        return 2
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
