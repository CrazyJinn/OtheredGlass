"""台词 JSONL（创作区 SecScript 产物）的唯一读写/校验/投影实现。

文件：`25_剧本/chapter<NN>_<章概述>/sec<MM>_<节概述>/台词.jsonl`（UTF-8，每行一个 JSON 对象）。

行类型 8 种（op 字段区分）：
  meta    首行保留行：{op, chapter, title, requires{characters,scenes,portraits}, line_seq}
  scene   场景分隔行：{op, id, scene, time?}——到下一 scene 行或 EOF 为一个 scene-block
  say     台词行：{id, op, who, portrait, pos, text, audio?}（四字段必填；不含 emotion/voice）
  narrate 旁白行：{id, op, text}
  choice/label/jump/ending  分支控制行：{id, op, ...}（结构同运行时章 JSON 的同名 op）
感官演出 op（bgm/bg/sfx/show/hide）**不入台词文件**——BGM 走图 `Scene-has_bgm->BgmTrack`
发布时注入 scene-block；背景 = scene 行的 scene 名；立绘出场 = say 自带槽位。

单句修改契约：改一行只碰一行——save 逐行 `json.dumps(ensure_ascii=False)` 序列化，
未修改的行保持原字节；所有写回方（voice_bundler bind-audio、dashboard 审批动作）
**一律走本模块**，禁止裸写（dumps 参数不一致会污染全文件 diff）。

行 id：`L<NNNN>` 节内递增、**永不复用**；水位在 meta.line_seq（下一个可分配号）。
手改/LLM 插入行 = 取当前水位作 id 且 meta.line_seq+=1；删行不动水位。
voice key 挂在 say 行 `audio.key`（voice_bundler.make_voice_key 产，末段=行 id），
插入/删除/移动行不改变其他行的 key——这是替代旧 line_idx 位置寻址的核心。

audio 对象（say 行，配音后处理注入）：{key, emotion, status, attempts, text_sha1}
  status ∈ pending/approved/rejected（行级审批三态，非图字段）
  text_sha1 = 生成时台词的 sha1——判「台词改了没」（stale）的唯一依据，不做 normalize
"""
import hashlib
import json
import re
from pathlib import Path

AUDIO_STATUS = ("pending", "approved", "rejected")
LINE_OPS = ("say", "narrate", "choice", "label", "jump", "ending")
ALL_OPS = ("meta", "scene") + LINE_OPS
POS_VALUES = ("left", "center", "right")
_LINE_ID_RE = re.compile(r"^L(\d+)$")


def text_sha1(text: str) -> str:
    """台词文本指纹（stale 判定依据）。不做 normalize——任何字符改动（含空格）都判变。"""
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()


# ── 读写 ──

def load(path) -> list:
    """读 JSONL → rows（list[dict]）。任何一行解析失败抛 ValueError（带行号）。"""
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"第 {i} 行不是合法 JSON：{e}") from e
    return rows


def save(path, rows) -> None:
    """逐行序列化写回。未修改的行字节不变（单句修改只 diff 一行的保证）。"""
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    Path(path).write_text(text, encoding="utf-8")


# ── 遍历与行 id ──

def iter_say_rows(rows):
    """遍历 say 行，yield (scene_id, row)。scene_id 取该行所属 scene 分隔行的 id。"""
    cur_scene = None
    for r in rows:
        op = r.get("op")
        if op == "scene":
            cur_scene = r.get("id", "")
        elif op == "say":
            yield cur_scene, r


def line_seq(rows) -> int:
    """当前水位（meta.line_seq，下一个可分配号）。"""
    meta = rows[0] if rows and rows[0].get("op") == "meta" else {}
    return int(meta.get("line_seq", 0))


def next_line_id(rows) -> str:
    """当前水位对应的下一个行 id（如 'L0033'）。只读不分配。"""
    return f"L{line_seq(rows):04d}"


def alloc_line_id(rows) -> str:
    """分配一个新行 id 并推进水位（插入新行时用）。改 rows[0].line_seq。"""
    meta = rows[0]
    nid = f"L{int(meta.get('line_seq', 0)):04d}"
    meta["line_seq"] = int(meta.get("line_seq", 0)) + 1
    return nid


def find_row(rows, line_id):
    """按行 id 找台词行（不含 meta/scene）。找不到返回 None。"""
    for r in rows:
        if r.get("id") == line_id and r.get("op") in LINE_OPS:
            return r
    return None


# ── 行级状态（音频审批三态 + stale 判定）──

def line_state(row) -> str:
    """say 行的音频状态分类：missing（无 audio）/ approved / rejected / pending / stale
    （audio 存在但 text_sha1 ≠ sha1(当前 text)，台词改过需重配）。非 say 行返回 ''。"""
    if row.get("op") != "say":
        return ""
    audio = row.get("audio")
    if not isinstance(audio, dict) or not audio.get("key"):
        return "missing"
    if audio.get("text_sha1") != text_sha1(row.get("text", "")):
        return "stale"
    return audio.get("status") or "pending"


def needs_regen(rows, only=("missing", "rejected", "stale")):
    """需（重）生成的 say 行：[{scene_id, id, who, text, reason}]。"""
    out = []
    for scene_id, r in iter_say_rows(rows):
        st = line_state(r)
        if st in only:
            out.append({
                "scene_id": scene_id, "id": r["id"],
                "who": r.get("who", ""), "text": r.get("text", ""), "reason": st,
            })
    return out


def set_audio(rows, line_id, *, key=None, emotion=None, status=None, attempts=None, resha1=False):
    """写单个 say 行的 audio 字段（merge 语义，仅覆盖传入的字段）。

    dashboard 审批动作用 status=；bind-audio 用 key/emotion/status='pending'/
    attempts=旧+1/resha1=True。返回是否命中。
    """
    row = find_row(rows, line_id)
    if row is None:
        return False
    audio = row.get("audio")
    if not isinstance(audio, dict):
        audio = {}
        row["audio"] = audio
    if key is not None:
        audio["key"] = key
    if emotion is not None:
        audio["emotion"] = emotion
    if status is not None:
        audio["status"] = status
    if attempts is not None:
        audio["attempts"] = attempts
    if resha1:
        audio["text_sha1"] = text_sha1(row.get("text", ""))
    return True


def reset_all_audio(rows):
    """整节驳回：全部 say 行 audio 归 pending（重配语义）。返回重置行数。"""
    n = 0
    for _, r in iter_say_rows(rows):
        audio = r.get("audio")
        if isinstance(audio, dict) and audio.get("status") != "pending":
            audio["status"] = "pending"
            n += 1
    return n


def audio_counts(rows) -> dict:
    """say 行音频状态统计（节级审批 gate 用）。"""
    c = {"say": 0, "missing": 0, "pending": 0, "approved": 0, "rejected": 0, "stale": 0}
    for _, r in iter_say_rows(rows):
        c["say"] += 1
        c[line_state(r)] = c.get(line_state(r), 0) + 1
    return c


def all_approved(rows) -> bool:
    """节级通过 gate：全部 say 行 approved（missing/pending/rejected/stale 均不允许）。"""
    c = audio_counts(rows)
    return c["say"] > 0 and c["approved"] == c["say"]


# ── 投影：JSONL rows → 运行时章 JSON 片段 ──

def project(rows) -> dict:
    """投影为 {meta, scenes}（与运行时章 JSON 同构，供 merge/schema 校验）。

    - meta 行 → 顶层 meta（丢 op/line_seq）
    - scene 行 → scenes 元素 {id, scene, time?}（bgm 由发布工具按图注入，此处不产）
    - 台词行 → 丢 id/audio；say 行 audio.key → voice；**不投 emotion**（运行时不消费）
    - 首个台词行之前必须有 scene 行（否则 raise ValueError）
    """
    if not rows or rows[0].get("op") != "meta":
        raise ValueError("首行必须是 meta 行")
    meta = {k: v for k, v in rows[0].items() if k not in ("op", "line_seq")}
    scenes, cur = [], None
    for r in rows[1:]:
        op = r.get("op")
        if op == "meta":
            continue
        if op == "scene":
            cur = {"id": r.get("id", ""), "scene": r.get("scene", "")}
            if r.get("time"):
                cur["time"] = r["time"]
            scenes.append(cur)
            continue
        if cur is None:
            raise ValueError(f"行 {r.get('id', '?')}（op={op}）出现在首个 scene 行之前")
        line = {k: v for k, v in r.items() if k not in ("id", "audio")}
        if op == "say":
            audio = r.get("audio")
            if isinstance(audio, dict) and audio.get("key"):
                line["voice"] = audio["key"]
        cur.setdefault("lines", []).append(line)
    return {"meta": meta, "scenes": scenes}


# ── 校验 ──

def validate_rows(rows) -> list:
    """行级校验（不含 schema）。返回错误列表（空 = 通过）。"""
    errors = []
    if not rows:
        return ["文件为空（缺 meta 首行）"]
    if rows[0].get("op") != "meta":
        errors.append("首行必须是 meta 行")
    metas = [r for r in rows if r.get("op") == "meta"]
    if len(metas) > 1:
        errors.append(f"meta 行只能有一个（发现 {len(metas)} 个）")
    seq = None
    if metas:
        seq = metas[0].get("line_seq")
        if not isinstance(seq, int) or seq < 1:
            errors.append(f"meta.line_seq 必须是正整数（当前 {seq!r}）")
        for k in ("chapter", "title"):
            v = metas[0].get(k)
            if v is None or v == "":
                errors.append(f"meta.{k} 必填")  # chapter=0（序章）是合法值，不按 falsy 判

    seen_line_ids, seen_scene_ids = set(), set()
    has_scene = False
    cur_scene = ""
    for i, r in enumerate(rows, 1):
        op = r.get("op")
        if op not in ALL_OPS:
            errors.append(f"第 {i} 行：未知 op {op!r}（允许 {ALL_OPS}）")
            continue
        if op == "meta":
            continue
        if op == "scene":
            has_scene = True
            cur_scene = r.get("id") or ""
            if not r.get("id") or not r.get("scene"):
                errors.append(f"第 {i} 行：scene 行 id/scene 必填")
            elif r["id"] in seen_scene_ids:
                errors.append(f"第 {i} 行：scene id {r['id']!r} 节内重复")
            else:
                seen_scene_ids.add(r["id"])
            continue
        # 台词行
        rid = r.get("id")
        m = _LINE_ID_RE.match(rid or "")
        if not m:
            errors.append(f"第 {i} 行：行 id 必须形如 L0001（当前 {rid!r}）")
        else:
            if rid in seen_line_ids:
                errors.append(f"第 {i} 行：行 id {rid} 重复")
            seen_line_ids.add(rid)
            if isinstance(seq, int) and int(m.group(1)) >= seq:
                errors.append(
                    f"第 {i} 行：行 id {rid} 数值 ≥ 水位 line_seq={seq}"
                    "（手改插入行须取当前水位作 id 并 +1，见 jsonl_script 模块说明）"
                )
        if not has_scene:
            errors.append(f"第 {i} 行：台词行出现在首个 scene 行之前")
        if op == "say":
            for k in ("who", "portrait", "pos", "text"):
                if not r.get(k):
                    errors.append(f"第 {i} 行（say {rid}）：字段 {k} 必填")
            if r.get("pos") and r["pos"] not in POS_VALUES:
                errors.append(f"第 {i} 行（say {rid}）：pos 必须 ∈ {POS_VALUES}")
            for k in ("emotion", "voice"):
                if k in r:
                    errors.append(f"第 {i} 行（say {rid}）：不得写 {k}（emotion 由配音期判别入 audio.emotion；voice 由 audio.key 投影）")
            audio = r.get("audio")
            if audio is not None:
                if not isinstance(audio, dict):
                    errors.append(f"第 {i} 行（say {rid}）：audio 必须是对象")
                else:
                    if not audio.get("key"):
                        errors.append(f"第 {i} 行（say {rid}）：audio.key 必填")
                    if audio.get("status") not in AUDIO_STATUS:
                        errors.append(f"第 {i} 行（say {rid}）：audio.status ∈ {AUDIO_STATUS}")
                    if "text_sha1" not in audio:
                        errors.append(f"第 {i} 行（say {rid}）：audio.text_sha1 必填")
        elif op == "narrate":
            if not r.get("text"):
                errors.append(f"第 {i} 行（narrate {rid}）：text 必填")
    return errors


def validate(path, schema_path=None) -> tuple:
    """完整校验：行级规则 + （可选）投影后走运行时章 JSON schema（jsonschema）。
    返回 (ok, errors)。"""
    try:
        rows = load(path)
    except (OSError, ValueError) as e:
        return False, [f"读取/解析失败：{e}"]
    errors = validate_rows(rows)
    if schema_path:
        try:
            doc = project(rows)
        except ValueError as e:
            errors.append(f"投影失败：{e}")
            return False, errors
        try:
            import jsonschema
            schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        except (OSError, ValueError, ImportError) as e:
            errors.append(f"schema 加载失败：{e}")
            return False, errors
        seen = set()

        def _add(loc, msg):
            key = (loc, msg)
            if key not in seen:
                seen.add(key)
                errors.append(f"{loc}: {msg}")

        for err in jsonschema.Draft202012Validator(schema).iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            _add(loc, err.message)
            for sub in err.context or []:
                sub_loc = "/".join(str(p) for p in sub.absolute_path) or loc
                _add(sub_loc, sub.message)
    return (len(errors) == 0), errors
