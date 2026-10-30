#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把本地 git 提交按顺序用 GitHub Data API 推上去，绕开 github.com 的上行问题。

本机实测：`git push` 会 `curl 55 Send failure: Connection was reset`，
而 `api.github.com` 只要 0.28 秒。这个脚本就走后者：
  git/blobs（按内容缓存，重复 blob 不重传）→ git/trees → git/commits（parents 串起来）
  → 最后一次性把分支指到最新提交。

跑法：
  python push_via_api.py                      # 推当前分支到 origin 对应的仓库
  python push_via_api.py --branch main --dry
前提：`gh auth token` 能拿到 token，且远端仓库已存在（空库也行）。
"""
import argparse, base64, json, os, subprocess, sys, time
import urllib.request

API = "https://api.github.com"
OWNER_REPO = os.environ.get("PUSH_REPO", "")   # 形如 openclawzhangchong/jiushouji-yuyin-gaizao


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          check=True).stdout


def token():
    t = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if t:
        return t
    return sh("gh", "auth", "token").strip()


def api(method, path, tok, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Authorization": "Bearer " + tok,
                                          "Accept": "application/vnd.github+json",
                                          "User-Agent": "push_via_api"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        detail = ""
        try:
            detail = e.read().decode()[:300]
        except Exception:
            pass
        raise RuntimeError("%s %s 失败：%s %s" % (method, path, e, detail))


def repo_from_remote():
    for line in sh("git", "remote", "-v").splitlines():
        if "(push)" in line:
            u = line.split()[1]
            for pre in ("https://github.com/", "git@github.com:"):
                if pre in u:
                    p = u.split(pre, 1)[1]
                    return p[:-4] if p.endswith(".git") else p
    sys.exit("找不到 github.com 的 push remote，或设 PUSH_REPO=owner/name")


def is_empty_repo(e):
    return "Git Repository is empty" in str(e)


def bootstrap(repo, tok, first_commit):
    """GitHub 的 Git Data API 对完全空库一律返 409，必须先用 Contents API 造出第一个提交。
    这一步会在远端多出一个只含 README 的占位提交，属正常代价。"""
    files = sh("git", "ls-tree", "-r", "--name-only", first_commit).split("\n")
    readme = None
    for cand in ("README.md",) + (".gitignore",):
        if cand in files:
            readme = cand
            break
    if readme is None:
        raise RuntimeError("空库 bootstrap 需要一个 README.md 或 .gitignore 作为首个提交的文件")
    raw = subprocess.run(["git", "show", "%s:%s" % (first_commit, readme)],
                         capture_output=True, check=True).stdout
    body = {"message": "建仓占位：先提交 %s（GitHub Git Data API 不接受空库）" % readme,
            "content": base64.b64encode(raw).decode()}
    r = api("PUT", "/repos/%s/contents/%s" % (repo, readme), tok, body)
    sha = r["commit"]["sha"]
    print("  空库已 bootstrap，首个提交 %s" % sha[:8])
    return sha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="main")
    ap.add_argument("--repo", default=OWNER_REPO or None)
    ap.add_argument("--dry", action="store_true", help="只报告要推什么，不动远端")
    a = ap.parse_args()

    repo = a.repo or repo_from_remote()
    tok = token()
    if not repo:
        sys.exit("仓库未确定")

    commits = sh("git", "log", "--reverse", "--format=%H", a.branch).split()
    if not commits:
        sys.exit("分支 %s 上没有提交" % a.branch)
    print("仓库 %s  分支 %s  待推提交 %d 个" % (repo, a.branch, len(commits)))
    for c in commits:
        print("  %s %s" % (c[:8], sh("git", "log", "-1", "--format=%s", c).strip()))
    if a.dry:
        return 0

    blob_cache = {}
    parent = []
    try:                                 # 远端分支已存在 -> 从它的 HEAD 接着长，并跳过重推
        head = api("GET", "/repos/%s/commits/%s" % (repo, a.branch), tok)
        parent = [head["sha"]]
        have = set()
        for cc in api("GET", "/repos/%s/commits?per_page=100&sha=%s" % (repo, a.branch), tok):
            have.add(cc["commit"]["message"].splitlines()[0])
        keep = [c for c in commits
                if sh("git", "log", "-1", "--format=%s", c).strip() not in have]
        print("远端已有 %s，跳过重推 %d 个提交" % (parent[0][:8], len(commits) - len(keep)))
        commits = keep
        if not commits:
            print("没有需要推的提交")
            return 0
    except RuntimeError as e:
        if not is_empty_repo(e):
            raise
        parent = [bootstrap(repo, tok, commits[0])]

    for c in commits:
        entries = []
        fresh = 0
        for ln in sh("git", "ls-tree", "-r", c).splitlines():
            meta, path = ln.split("\t", 1)
            mode, typ, sha = meta.split()
            if typ != "blob":
                raise RuntimeError("暂不支持非 blob 条目：" + ln)
            if sha in blob_cache:
                entries.append({"path": path, "mode": mode, "type": "blob",
                                "sha": blob_cache[sha]})
                continue
            raw = subprocess.run(["git", "cat-file", "blob", sha],
                                 capture_output=True, check=True).stdout
            r = api("POST", "/repos/%s/git/blobs" % repo, tok,
                    {"content": base64.b64encode(raw).decode(), "encoding": "base64"})
            blob_cache[sha] = r["sha"]
            fresh += 1
            entries.append({"path": path, "mode": mode, "type": "blob", "sha": r["sha"]})
        print("  提交 %s：%d 个文件，其中新上传 blob %d 个" % (c[:8], len(entries), fresh))

        tree = api("POST", "/repos/%s/git/trees" % repo, tok, {"tree": entries})["sha"]
        msg = sh("git", "log", "-1", "--format=%B", c).rstrip("\n")
        author = sh("git", "log", "-1", "--format=%an|%ae|%aI", c).strip().split("|")
        body = {"message": msg, "tree": tree,
                "author": {"name": author[0], "email": author[1], "date": author[2]}}
        if parent:
            body["parents"] = parent
        new = api("POST", "/repos/%s/git/commits" % repo, tok, body)["sha"]
        print("  远端提交 %s <- %s" % (new[:8], c[:8]))
        parent = [new]
        time.sleep(0.3)

    ref = "refs/heads/" + a.branch
    # 坑：git/ref 和 git/refs 这两个端点要传 heads/<branch>，
    # 传 refs/heads/<branch> 会 404，然后被误判成"分支不存在"去走创建，再撞 422 already exists
    short = "heads/" + a.branch
    try:
        api("GET", "/repos/%s/git/ref/%s" % (repo, short), tok)
        api("PATCH", "/repos/%s/git/refs/%s" % (repo, short), tok, {"sha": parent[0]})
        print("分支 %s 已前移到 %s" % (ref, parent[0][:8]))
    except RuntimeError as e:
        if not is_empty_repo(e) and "not found" not in str(e).lower():
            raise
        api("POST", "/repos/%s/git/refs" % repo, tok, {"ref": ref, "sha": parent[0]})
        print("已创建 %s -> %s" % (ref, parent[0][:8]))

    print("\n远端 HEAD 校验：")
    head = api("GET", "/repos/%s/commits/%s" % (repo, a.branch), tok)
    print("  " + head["sha"][:8] + "  " + head["commit"]["message"].splitlines()[0])
    print("  文件数 %d" % len(api("GET", "/repos/%s/git/trees/%s?recursive=1"
                                  % (repo, head["sha"]), tok)["tree"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
