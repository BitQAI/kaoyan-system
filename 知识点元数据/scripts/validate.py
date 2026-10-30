#!/usr/bin/env python3
"""校验元数据：E 码（阻断）/ W 码（警告）。

用法：python scripts/validate.py [--json]
"""
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
META = ROOT / '知识点元数据'

SUBJECTS = ['812', '315', '101', '204']
TAGS_BY_SUBJECT = {
    '812': {'基础', '重点', '易错', '机制'},
    '315': {'必掌握', '理解', '了解', '高频', '常考'},
    '101': {'高频', '常考', '易错', '重点', '基础'},
    '204': {'词汇', '句型', '技巧', '模板', '高频', '易错'},
}
PRIORITIES = {'★', '●', '○'}
MODULES = {
    '101': {'马原', '毛中特', '习概', '史纲', '思修法治', '时政当代'},
    '204': {'考试结构', '词汇语法', '完形', '阅读A', '阅读B', '翻译', '写作A', '写作B'},
    '315': {'无机及分析化学', '有机化学'},
    '812': {'植物生理学'},
}
ID_RE = re.compile(r'^(101|204|315|812)(\d{2})(\d{2}|M\d{2})$')
FORMULA_BAD = re.compile(r'\b[A-Z][a-z]?\d+[A-Za-z]*\b')
KINDS_BY_SUBJECT = {
    '812': {'名解', '简答', '论述'},
    '315': {'选择', '填空', '计算', '分析', '合成'},
    '101': {'名词解释', '简答', '分析'},
    '204': {'词汇', '句型', '技巧', '模板', '回译', '默写'},
}
QUOTA_812 = {'名解': 2, '简答': 2, '论述': 1}
CARD_TYPES = {'定义', '原理', '条件', '公式', '过程', '辨析', '应用', '易错', '记忆'}
EVIDENCE_LEVELS = {'verified', 'inferred', 'pending'}


def load_unit_registry(sid='812'):
    """读取 coverage.md 的「理解性补充 unit 清单」，返回 {(point_id, unit_index)}。"""
    p = META / 'research' / f'{sid}-coverage.md'
    if not p.exists():
        return set()
    reg, in_sec = set(), False
    for line in p.read_text(encoding='utf-8').splitlines():
        if line.startswith('## 理解性补充'):
            in_sec = True
            continue
        if in_sec and line.startswith('## '):
            break
        if in_sec:
            m = re.match(r'^\| (\S+) \| (\d+) \|', line)
            if m:
                reg.add((m.group(1), int(m.group(2))))
    return reg


#: 结构化卡片 payload 的必填字段（词卡 / 词组卡 / 辨析卡）
PAYLOAD_REQUIRED = {
    'word': ('word', 'meanings', 'examples'),
    'phrase': ('word', 'meanings'),
    'confusable': ('group', 'diff'),
}
CLOZE_BLANK = '____'


def check_payload(sid, pid, card):
    """E24：payload 结构不合法或缺必填字段；没有 payload 视为普通卡。"""
    p = card.get('payload')
    if p is None:
        return []
    if not isinstance(p, dict):
        return [f'E28 {sid}: {pid} payload 不是对象']
    kind = p.get('type')
    if kind not in PAYLOAD_REQUIRED:
        return [f'E28 {sid}: {pid} payload.type 非法 {kind!r}']
    errs = []
    for key in PAYLOAD_REQUIRED[kind]:
        if p.get(key) in (None, '', [], {}):
            errs.append(f'E28 {sid}: {pid} payload 缺 {key}')
    group = p.get('group')
    if kind == 'confusable' and isinstance(group, list) and len(group) < 2:
        errs.append(f'E24 {sid}: {pid} 辨析组少于 2 个词')
    return errs


def check_cloze(sid, pid, card):
    """E25：默写卡的空格数与 answer_points 数量必须一致。"""
    if card.get('kind') != '默写':
        return []
    blanks = (card.get('question') or '').count(CLOZE_BLANK)
    answers = card.get('answer_points') or []
    if blanks != len(answers):
        return [f'E29 {sid}: {pid} 默写空格 {blanks} 个，答案 {len(answers)} 个']
    return []


def validate_v3(sid, d, errors, warns):
    """ky-point/3.0 专属校验：原子卡、关联、证据。"""
    pts = d['points']
    registered = load_unit_registry(sid)
    by_id = {p['id']: p for p in pts}
    seen_order = collections.defaultdict(set)
    all_q = collections.defaultdict(list)

    for p in pts:
        pid = p['id']
        o = p.get('order')
        if not isinstance(o, int) or o < 1:
            errors.append(f'E27 {sid}: {pid} order 非法 {o!r}')
        elif o in seen_order[p.get('chapter')]:
            errors.append(f'E27 {sid}: {p.get("chapter")} order 重复 {o}')
        else:
            seen_order[p.get('chapter')].add(o)

        for f in ('prerequisites', 'related'):
            for rid in p.get(f) or []:
                if rid == pid or rid not in by_id:
                    errors.append(f'E25 {sid}: {pid} {f} 指向无效 {rid}')
        for c in p.get('confusables') or []:
            rid = c.get('point_id')
            if rid and (rid == pid or rid not in by_id):
                errors.append(f'E25 {sid}: {pid} confusables 指向无效 {rid}')
            if not c.get('distinction'):
                errors.append(f'E25 {sid}: {pid} confusables 缺 distinction')

        ev = p.get('exam_evidence') or {}
        if ev.get('level') not in EVIDENCE_LEVELS:
            errors.append(f'E26 {sid}: {pid} exam_evidence.level 非法')
        if ev.get('level') != 'pending' and not ev.get('sources'):
            errors.append(f'E26 {sid}: {pid} exam_evidence 缺 sources')

        covered = set()
        n_units = len(p.get('units') or [])
        for c in p.get('cards') or []:
            ct = c.get('card_type')
            if ct not in CARD_TYPES:
                errors.append(f'E21 {sid}: {pid} card_type 非法 {ct!r}')
            ap = c.get('answer_points')
            if not isinstance(ap, list) or not ap:
                errors.append(f'E22 {sid}: {pid} answer_points 为空')
            refs = c.get('unit_refs')
            if not isinstance(refs, list) or not refs:
                errors.append(f'E23 {sid}: {pid} unit_refs 为空')
            else:
                for r in refs:
                    if not isinstance(r, int) or not (1 <= r <= n_units):
                        errors.append(f'E23 {sid}: {pid} unit_refs 越界 {r} (units={n_units})')
                    else:
                        covered.add(r)
                if len(refs) > 3:
                    warns.append(f'W18 {sid}: {pid} 单卡覆盖 {len(refs)} 个 unit')
            q = re.sub(r'\s+', '', c.get('question') or '')
            all_q[q].append(pid)
            if c.get('kind') in ('名解', '简答') and len(c.get('question') or '') > 120:
                warns.append(f'W15 {sid}: {pid} 设问过长 {len(c["question"])}')
            if c.get('kind') in ('简答', '论述') and len(ap or []) < 2:
                warns.append(f'W16 {sid}: {pid} answer_points 少于 2 条')
            a = re.sub(r'\s+', '', c.get('answer') or '')
            an = re.sub(r'\s+', '', c.get('analysis') or '')
            if a and an and a in an and len(a) / max(len(an), 1) > 0.8:
                warns.append(f'W19 {sid}: {pid} analysis 复述 answer')

        for m in p.get('media') or []:
            if not (m.get('caption') or '').strip():
                warns.append(f'W20 {sid}: {pid} media 缺 caption')
            if not (m.get('alt') or '').strip():
                warns.append(f'W20 {sid}: {pid} media 缺 alt')
            if m.get('kind') == 'diagram' and not (m.get('svg') or m.get('src')):
                warns.append(f'W20 {sid}: {pid} diagram 缺 svg/src')

        for i in range(1, n_units + 1):
            if i not in covered and (pid, i) not in registered:
                warns.append(f'W17 {sid}: {pid} unit {i} 未被卡片覆盖')

    for q, owners in all_q.items():
        if q and len(owners) > 1:
            errors.append(f'E24 {sid}: 重复设问 {q[:30]}… 出现在 {owners}')


def analysis_consistent(answer: str, analysis: str) -> bool:
    wrong, right = set(), set()
    for m in re.finditer(
            r'(?:选项|项)?\s*([A-D])\s*(?:项|说法|叙述)?\s*(?:是|为)?\s*'
            r'(错|错误|不正确|不对|不符合)', analysis):
        wrong.add(m.group(1))
    for m in re.finditer(
            r'(?:选项|项)?\s*([A-D])\s*(?:项|说法|叙述)?\s*(?:是|为)?\s*'
            r'(正确|对|符合)', analysis):
        right.add(m.group(1))
    if answer in wrong:
        return False
    if right and answer not in right:
        return False
    return True


def main():
    errors, warns, stats = [], [], {}
    all_ids = set()
    all_card_ids = set()
    for sid in SUBJECTS:
        jf = META / 'subjects' / sid / f'{sid}.json'
        if not jf.exists():
            errors.append(f'E00 {sid}: 缺少 {jf.name}')
            continue
        d = json.loads(jf.read_text(encoding='utf-8'))
        chaps = {c['id']: c for c in d['chapters']}
        pts = d['points']
        s = {'chapters': len(chaps), 'points': len(pts),
             'units': sum(len(p.get('units') or []) for p in pts),
             'cards': sum(len(p.get('cards') or []) for p in pts),
             'priority': {}, 'tags': {}, 'with_explain': 0,
             'with_title': 0, 'tts_enabled': 0}
        answers = collections.Counter()
        chap_kinds = collections.defaultdict(collections.Counter)
        for p in pts:
            pid = p['id']
            # E02 id 格式 / 唯一 / 前缀
            m = ID_RE.match(pid)
            if not m:
                errors.append(f'E02 {sid}: id 格式非法 {pid}')
            elif m.group(1) != sid:
                errors.append(f'E02 {sid}: id 前缀与科目不符 {pid}')
            if pid in all_ids:
                errors.append(f'E02 {sid}: id 全局重复 {pid}')
            all_ids.add(pid)
            # E03 chapter 引用
            if p.get('chapter') not in chaps:
                errors.append(f'E03 {sid}: {pid} chapter 不存在 {p.get("chapter")}')
            # E04 必填
            for f in ('point', 'title', 'explain', 'exam', 'priority', 'source'):
                if not p.get(f):
                    errors.append(f'E04 {sid}: {pid} 必填字段为空 {f}')
            if not p.get('keywords'):
                errors.append(f'E04 {sid}: {pid} keywords 为空')
            if not (p.get('source') or {}).get('ref'):
                errors.append(f'E04 {sid}: {pid} source.ref 为空')
            # E05 长度（机制点 M 后缀为因果链，允许更长）
            limit = 200 if 'M' in pid[-3:] else 120
            if len(p.get('point') or '') > limit:
                warns.append(f'W03 {sid}: {pid} point 超长 {len(p["point"])} > {limit}')
            if len(p.get('title') or '') > 20:
                warns.append(f'W04 {sid}: {pid} title 超长 {len(p["title"])}')
            # E06 priority / tags
            if p.get('priority') not in PRIORITIES:
                errors.append(f'E06 {sid}: {pid} priority 非法 {p.get("priority")}')
            else:
                s['priority'][p['priority']] = s['priority'].get(p['priority'], 0) + 1
            for t in (p.get('tags') or []):
                s['tags'][t] = s['tags'].get(t, 0) + 1
                if t not in TAGS_BY_SUBJECT[sid]:
                    errors.append(f'E06 {sid}: {pid} tag 不在受控词表 {t}')
            if len(p.get('tags') or []) > 3:
                warns.append(f'W05 {sid}: {pid} tags 超过 3 个')
            # E07 溯源可回溯
            if not (p.get('source') or {}).get('file'):
                errors.append(f'E07 {sid}: {pid} source.file 为空')
            # E13 module
            for c in d['chapters']:
                if c.get('module') not in MODULES[sid]:
                    errors.append(f'E13 {sid}: {c["id"]} module 不在受控词表 {c.get("module")}')
            # E12 冲突
            if p.get('priority') == '○' and ('必掌握' in (p.get('tags') or []) or
                                             '重点' in (p.get('tags') or [])):
                errors.append(f'E12 {sid}: {pid} priority=○ 但含必掌握/重点')
            # W01 同章重复
            if p.get('explain'):
                s['with_explain'] += 1
            if p.get('title'):
                s['with_title'] += 1
            if (p.get('tts') or {}).get('enabled'):
                s['tts_enabled'] += 1
            # W08 ASCII 公式残留
            bad = [x for x in FORMULA_BAD.findall(p.get('point') or '')
                   if x not in ('SN1', 'SN2', 'E1', 'E2')]
            if bad:
                warns.append(f'W08 {sid}: {pid} 疑似 ASCII 化学式残留 {set(bad)}')
            # E14 card_id 唯一 + 格式；E16/E17 卡片题型与解析
            card_ids = set()
            for i, c in enumerate(p.get('cards') or []):
                cid = c.get('card_id') or ''
                if not cid:
                    errors.append(f'E14 {sid}: {pid} 第 {i + 1} 张卡缺 card_id')
                    continue
                if cid in all_card_ids:
                    errors.append(f'E14 {sid}: {pid} card_id 全局重复 {cid}')
                all_card_ids.add(cid)
                card_ids.add(cid)
                if cid != f'c{pid}-{i + 1}':
                    errors.append(f'E14 {sid}: {pid} card_id 格式应为 c{pid}-{i + 1}，实为 {cid}')

                kind = c.get('kind') or ''
                question = c.get('question') or c.get('front') or ''
                answer = c.get('answer') or c.get('back') or ''
                analysis = c.get('analysis') or ''
                if kind not in KINDS_BY_SUBJECT[sid]:
                    errors.append(f'E16 {sid}: {pid} 卡片 kind 非法 {kind}')
                if not question or not answer:
                    errors.append(f'E16 {sid}: {pid} 卡片 question/answer 为空')
                if len(analysis) < 30:
                    errors.append(f'E16 {sid}: {pid} 卡片 analysis 过短 {len(analysis)}')
                if kind == '选择':
                    opts = c.get('options') or []
                    if len(opts) != 4 or len({re.sub(r'^[A-D]\s*[.、．]\s*', '', o) for o in opts}) != 4:
                        errors.append(f'E17 {sid}: {pid} 选择题选项不是 4 个互异项')
                    if answer not in ('A', 'B', 'C', 'D'):
                        errors.append(f'E17 {sid}: {pid} 选择题答案非 A–D：{answer!r}')
                    elif not analysis_consistent(answer, analysis):
                        errors.append(f'E17 {sid}: {pid} 选择题答案与解析字母矛盾')
                    answers[answer] += 1
                else:
                    if c.get('options'):
                        errors.append(f'E17 {sid}: {pid} 非选择题不应带 options')
                errors.extend(check_payload(sid, pid, c))
                errors.extend(check_cloze(sid, pid, c))
                chap_kinds[p.get('chapter')][kind] += 1

            # E18 listen 代表题
            listen = p.get('listen') or {}
            if not listen.get('script'):
                errors.append(f'E18 {sid}: {pid} listen.script 为空')
            elif listen.get('card_id') not in card_ids:
                errors.append(f'E18 {sid}: {pid} listen.card_id 不存在 {listen.get("card_id")}')
            if listen.get('audio') not in ('ready', 'pending', 'none'):
                errors.append(f'E18 {sid}: {pid} listen.audio 非法 {listen.get("audio")}')

            # E19 exam_types 与卡片 kind 一致
            want_types = []
            for c in (p.get('cards') or []):
                if c.get('kind') and c['kind'] not in want_types:
                    want_types.append(c['kind'])
            if set(p.get('exam_types') or []) != set(want_types):
                errors.append(f'E19 {sid}: {pid} exam_types 与卡片 kind 不一致')
            # W11/W12 必出题型与填空形态
            if sid == '315':
                miss = {'选择', '填空'} - set(want_types)
                if miss:
                    warns.append(f'W11 315: {pid} 缺必出题型 {sorted(miss)}')
            if sid == '812':
                miss = {'名解', '简答'} - set(want_types)
                if miss:
                    warns.append(f'W12 812: {pid} 缺必出题型 {sorted(miss)}')
            if len(p.get('cards') or []) < 2 and sid in ('101', '204'):
                warns.append(f'W13 {sid}: {pid} 卡片少于 2 张')
            for c in (p.get('cards') or []):
                if c.get('kind') == '填空':
                    q = c.get('question') or ''
                    if '___' not in q and '（ ）' not in q and '____' not in q:
                        warns.append(f'W14 {sid}: {pid} 填空题无空位')
            # E15 音频落地：enabled 的点每段必须有 file 且文件存在
            tts = p.get('tts') or {}
            pending_audio = (d.get('schema') == 'ky-point/3.0'
                             and (p.get('listen') or {}).get('audio') == 'pending')
            if tts.get('enabled'):
                if not tts.get('clips'):
                    errors.append(f'E15 {sid}: {pid} tts.enabled 但无 clips')
                for c in tts.get('clips') or []:
                    rel = c.get('file')
                    if not rel:
                        if pending_audio:
                            continue
                        errors.append(f'E15 {sid}: {pid} clip {c.get("clip_id")} 缺 file')
                        continue
                    if not (META / rel).exists():
                        errors.append(f'E15 {sid}: {pid} 音频文件不存在 {rel}')
                    if not c.get('dur_sec'):
                        errors.append(f'E15 {sid}: {pid} clip {c.get("clip_id")} 缺实测 dur_sec')
        # E11 entry_count
        for c in d['chapters']:
            n = sum(1 for p in pts if p.get('chapter') == c['id'])
            if c.get('entry_count') != n:
                errors.append(f'E11 {sid}: {c["id"]} entry_count {c.get("entry_count")} ≠ 实际 {n}')
        # W09 无 unit 派生
        none_unit = [p['id'] for p in pts if not p.get('units')]
        if none_unit:
            warns.append(f'W09 {sid}: {len(none_unit)} 个知识点无 unit 派生')
        # E20 812 章级题型配额
        if sid == '812':
            for c in d['chapters']:
                cnt = chap_kinds.get(c['id'], {})
                for k, need in {'名解': 2, '简答': 2}.items():
                    if cnt.get(k, 0) < need:
                        errors.append(f'E20 812: {c["id"]} {k} 仅 {cnt.get(k, 0)} 张 < 配额 {need}')
                if c.get('tier') == 1 and cnt.get('论述', 0) < 1:
                    errors.append(f'E20 812: {c["id"]} 第一梯队章论述仅 {cnt.get("论述", 0)} 张 < 1')
        # W10 选择题答案分布
        total_ans = sum(answers.values())
        if total_ans >= 10:
            top_letter, top_n = answers.most_common(1)[0]
            if top_n / total_ans > 0.4:
                warns.append(f'W10 {sid}: 选择题答案偏斜 {top_letter}={top_n}/{total_ans}')
        stats[sid] = s
        if d.get('schema') == 'ky-point/3.0':
            validate_v3(sid, d, errors, warns)

    print('=' * 78)
    print(f"{'科目':<6}{'章':>4}{'点':>5}{'unit':>7}{'card':>6}   {'优先级 ★/●/○':<16}"
          f"{'有讲解':>7}{'可听':>6}")
    for sid in SUBJECTS:
        s = stats.get(sid)
        if not s:
            continue
        pr = s['priority']
        prio = f"{pr.get('★', 0)}/{pr.get('●', 0)}/{pr.get('○', 0)}"
        print(f"{sid:<6}{s['chapters']:>4}{s['points']:>5}{s['units']:>7}{s['cards']:>6}   "
              f"{prio:<16}{s['with_explain']:>7}{s['tts_enabled']:>6}")
    print('=' * 78)
    if warns:
        print(f'警告 {len(warns)} 条：')
        for w in warns[:20]:
            print('  ', w)
        if len(warns) > 20:
            print(f'   …其余 {len(warns) - 20} 条省略')
    if errors:
        print(f'\n错误 {len(errors)} 条：')
        for e in errors[:40]:
            print('  ', e)
        if len(errors) > 40:
            print(f'   …其余 {len(errors) - 40} 条省略')
        sys.exit(1)
    print('\n校验通过：0 错误')
    return stats


if __name__ == '__main__':
    main()
