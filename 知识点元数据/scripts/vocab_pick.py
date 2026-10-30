#!/usr/bin/env python3
"""词频选词：真题句子 → 1500 词表（本地统计，不联网）。

口径：语料中实词按出现次数排序，去功能词与过短词；不足 limit 时用补充词表
按给定顺序补齐，并标 in_corpus=false，供后续生成“非真题例句”。
"""
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[3]
META = ROOT / '知识点元数据'
SENTENCES = META / 'research' / '204-corpus' / 'sentences.jsonl'
OUT = META / 'subjects' / '204' / '204-vocab-list.jsonl'

TOKEN = re.compile(r"[A-Za-z][A-Za-z'-]+")

STOPWORDS = set("""
a about above after again against all also am an and any are as at be because been
before being below between both but by can could did do does doing down during each
few for from further had has have having he her here hers herself him himself his how
i if in into is it its itself just me more most my myself no nor not now of off on
once only or other our ours ourselves out over own same she should so some such than
that the their theirs them themselves then there these they this those through to too
under until up very was we were what when where which while who whom why will with
would you your yours yourself yourselves
""".split())

SUPPLEMENT = """
abandon abstract abundant accelerate access accommodate accompany accomplish accumulate
accurate achieve acknowledge acquire adapt adequate adjust administration admire adopt
advance advocate afford agriculture alter alternative ambiguous ambition analyse analysis
anticipate apparent appeal appropriate approve arbitrary architecture arise assess assign
assume attach attain attribute authority available awareness balance ban barrier
behaviour benefit bias boost boundary capable capacity career challenge character
circumstance civil claim clarify collapse combine comment commit commodity communicate
compensate compete complain complex component comprehensive compromise conceal concept
concern conclude conduct confine confirm conflict confront consequence considerable
consist constant constitute constrain construct consume contemporary context contribute
controversial conventional convert convey convince cooperate core corporate corruption
crisis critical crucial cultivate cumulative decline dedicate defect defence define delay
deliver demand demonstrate denial density deny depend deprive derive despite determine
develop device devote diminish discipline discourage dismiss display dispute distinct
distinguish distribute diverse dominate dramatic durable economy efficient eliminate
emerge emphasise employ enable encounter encourage endure enforce enhance enormous
ensure enterprise entitle environment equivalent essential establish estimate ethical
evaluate eventually evoke evolve exaggerate examine exceed exchange exclude exhibit
expand expense explicit exploit explore expose extend external extreme facilitate factor
favour feasible feature federal finance flexible focus forbid forecast formal former
formula foster foundation fragile framework frequency function fundamental generate
genuine globe grant guarantee guideline hesitate highlight hypothesis identify ignore
illustrate immune impact implement implication impose incentive incident incline
indicate inevitable influence inform initiative innovate insight inspire install
instance institute integrate integrity intend intense interact interpret interval
intervene introduce invest investigate involve isolate issue justify label labour
launch legal legislation legitimate liberal licence limit link literacy maintain
major manipulate margin mature maximum mechanism mediate method minimum modify monitor
motive mutual negative neglect negotiate network neutral nevertheless notion objective
obligation observe obtain obvious occupy occur offend offset operate oppose optimistic
option outcome overall overcome participate particular perceive perform permanent
persist perspective phase phenomenon policy portion possess potential practical precise
predict prefer prejudice preliminary preserve prestige presume prevail prevent primary
principle priority procedure proceed process profession prohibit prominent promote
prompt proportion prospect provide publish pursue qualify quote radical random range
rapid rare rate rational react recession recognise recommend recover reduce refer
reflect reform refuse regard region regulate reinforce reject relate rely remain remedy
remove render replace represent require resemble resist resolve resource respond
restore restrict retain reveal revenue reverse revise revolution reward rigid risk
routine rural satisfy scale scarce scheme scope secure seek select sensitive sequence
session severe shift significant similar simulate site situation sole solve source
specific specify stable standard statistics status strategy stress structure submit
subsequent substance substitute sufficient suggest summary supplement supply support
suppose surface survey survive suspend sustain symbol symptom target technique
temporary tendency tense terminate theme theory threat thrive tolerate transfer transform
transmit transport trend trigger ultimate underestimate undergo underlying undertake
uniform unique universal urban urge utility vague valid vary vast vehicle version
violate virtual visible vision vital volume voluntary welfare welfare widespread withdraw
withstand witness yield
""".split()


def pick(path: pathlib.Path, limit: int = 1500, min_freq: int = 2,
         supplemental: list[str] | None = None) -> list[dict]:
    freq: Counter = Counter()
    years: dict[str, set] = defaultdict(set)
    for line in pathlib.Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        year = row.get('year')
        for tok in TOKEN.findall(row.get('en') or ''):
            w = tok.lower().strip("-'")
            if len(w) < 3 or w in STOPWORDS:
                continue
            freq[w] += 1
            if year:
                years[w].add(int(year))
    ranked = sorted(
        ((w, n) for w, n in freq.items() if n >= min_freq),
        key=lambda x: (-x[1], x[0]))
    out = [{'word': w, 'freq': n, 'years': sorted(years[w]), 'in_corpus': True}
           for w, n in ranked[:limit]]
    have = {r['word'] for r in out}
    for w in (supplemental or []):
        if len(out) >= limit:
            break
        w = w.lower()
        if w in have or w in STOPWORDS or len(w) < 3:
            continue
        out.append({'word': w, 'freq': 0, 'years': [], 'in_corpus': False})
        have.add(w)
    return out


def main():
    limit = 1500
    rows = pick(SENTENCES, limit=limit, supplemental=SUPPLEMENT)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    in_corpus = sum(1 for r in rows if r['in_corpus'])
    print(f'写出 {OUT.relative_to(ROOT)}：{len(rows)} 词，'
          f'语料内 {in_corpus}，补充 {len(rows) - in_corpus}')


if __name__ == '__main__':
    sys.exit(main())
