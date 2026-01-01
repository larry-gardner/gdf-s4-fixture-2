"""GDF S4 agent job: the trusted packing steps (docs/GDF_MVP_01C_S4_PLAN.md §5.1, §5.5).

Run as `python3 -I <trusted checkout of main>/ci/pack.py ...`, never from the agent's workspace,
and never running Git or any other tool that reads configuration in that workspace.

  manifest WORKSPACE OUT                 the start tree, before the agent: path, kind, mode, sha256
  coding WORKSPACE MANIFEST OUTDIR NONCE EXIT TIMED_OUT SECONDS
                                         the changeset against the manifest, and result.json
  result OUTDIR ROLE NONCE EXIT TIMED_OUT SECONDS
                                         result.json only (the reviewer's)
  record OUTDIR NONCE BASELINE CANDIDATE DIGEST
                                         record.json (the record job's)

Links and special files in the workspace are refused (exit 3): nothing is packed.
"""
import hashlib
import json
import os
import re
import stat
import sys

RESULT_SCHEMA, RECORD_SCHEMA = "gdf-agent-result/v1", "gdf-agent-record/v1"
HEX = re.compile(r"[0-9a-f]+\Z")


def tree(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(dirnames + filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            info = os.lstat(path)
            if stat.S_ISDIR(info.st_mode):
                out[rel] = ["dir", 0, ""]
            elif stat.S_ISREG(info.st_mode):
                with open(path, "rb") as handle:
                    digest = hashlib.sha256(handle.read()).hexdigest()
                out[rel] = ["file", 1 if info.st_mode & 0o100 else 0, digest]
            else:
                raise SystemExit(3)                     # a link or special file: refuse
    return out


def write_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True)


def result(role, nonce, exit_code, timed_out, seconds, changes=None):
    value = {"schema": RESULT_SCHEMA, "role": role, "nonce": nonce,
             "exit_code": None if exit_code == "" else int(exit_code),
             "timed_out": timed_out == "true", "seconds": float(seconds)}
    if changes is not None:
        value["changes"] = changes
    return value


def main(argv):
    command, args = argv[1], argv[2:]
    if command == "manifest":
        workspace, out = args
        write_json(out, tree(workspace))
    elif command == "coding":
        workspace, manifest, outdir, nonce, exit_code, timed_out, seconds = args
        with open(manifest) as handle:
            start = json.load(handle)
        now = tree(workspace)
        changed = sorted(p for p, entry in now.items() if entry[0] == "file" and start.get(p) != entry)
        deleted = sorted(p for p, entry in start.items() if entry[0] == "file" and p not in now)
        for path in changed:
            source = os.path.join(workspace, path)
            target = os.path.join(outdir, "files", path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as handle:
                data = handle.read()
            with open(target, "xb") as handle:
                handle.write(data)
        changes = {"changed": [{"path": p, "executable": bool(now[p][1])} for p in changed], "deleted": deleted}
        write_json(os.path.join(outdir, "result.json"), result("coding", nonce, exit_code, timed_out, seconds, changes))
    elif command == "result":
        outdir, role, nonce, exit_code, timed_out, seconds = args
        write_json(os.path.join(outdir, "result.json"), result(role, nonce, exit_code, timed_out, seconds))
    elif command == "record":
        outdir, nonce, baseline, candidate, digest = args
        write_json(os.path.join(outdir, "record.json"), {"schema": RECORD_SCHEMA, "nonce": nonce,
                                                          "baseline_sha": baseline, "candidate_sha": candidate,
                                                          "diff_sha256": digest})
    else:
        raise SystemExit(2)


if __name__ == "__main__":
    main(sys.argv)
