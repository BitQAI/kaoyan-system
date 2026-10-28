#!/usr/bin/env python3
"""Task 2 RED/GREEN: 3.0 schema 必须接受 3.0 样本，2.0 schema 必须继续接受旧数据。"""
import json
import pathlib
import sys

import jsonschema

META = pathlib.Path(__file__).resolve().parents[2] / '知识点元数据'
S3 = META / 'schema/ky-point.schema.json'
S2 = META / 'schema/ky-point-2.0.schema.json'


def sample_v3():
    return {
        "schema": "ky-point/3.0", "subject": "812", "name": "植物生理学",
        "chapters": [{
            "id": "812-02", "name": "第二章", "module": "植物生理学",
            "tier": 1, "weight_center": 1, "weight_basis": "推算", "entry_count": 1,
        }],
        "points": [{
            "id": "8120201", "chapter": "812-02", "order": 1,
            "point": "水势的概念", "title": "水势", "explain": "水势是……",
            "exam": "名词解释;易错点", "keywords": ["水势", "渗透势", "压力势"],
            "priority": "★", "tags": [],
            "prerequisites": [], "related": [], "confusables": [],
            "exam_evidence": {"level": "pending", "basis": "待核", "sources": []},
            "source": {"kind": "html", "ref": "p4-2#x/p[0]/split[0]",
                       "file": "x.html", "section": "p4-2"},
            "spoken": "水势",
            "tts": {"enabled": False, "max_chars": 220, "est_sec": 0, "clips": []},
            "units": ["水势是水的化学势差。"],
            "exam_types": ["名解"],
            "listen": {"card_id": "c8120201-1", "kind": "名解",
                       "script": "设问", "audio": "pending"},
            "cards": [{
                "card_id": "c8120201-1", "kind": "名解", "card_type": "定义",
                "question": "名词解释：水势", "answer": "水势是……",
                "answer_points": ["水的化学势差", "表示水移动趋势"],
                "analysis": "答题结构：定义 + 物理意义 + 符号。常见失分点：把水势说成正值。",
                "unit_refs": [1], "difficulty": 2,
                "front": "名词解释：水势", "back": "水势是……", "point_id": "8120201",
            }],
        }],
    }


def sample_v2():
    return {
        "schema": "ky-point/2.0", "subject": "315", "name": "315 化学（农）",
        "chapters": [{
            "id": "315-01", "name": "第一章", "module": "无机及分析化学",
            "tier": 3, "weight_center": 3.0, "weight_basis": "推算", "entry_count": 1,
        }],
        "points": [{
            "id": "3150101", "chapter": "315-01", "point": "分散系", "title": "分散系",
            "explain": "分散系是……", "exam": "选择题", "keywords": ["分散系", "胶体", "粒径"],
            "priority": "●", "tags": [],
            "source": {"ref": "p3-4#x/p[0]/split[0]", "file": "x.html", "section": "p3-4"},
            "spoken": "分散系",
            "tts": {"enabled": False, "max_chars": 220, "est_sec": 0, "clips": []},
            "exam_types": ["选择"],
            "listen": {"card_id": "c3150101-1", "kind": "选择",
                       "script": "设问", "audio": "pending"},
            "cards": [{
                "card_id": "c3150101-1", "kind": "选择",
                "question": "下列属于胶体的是", "answer": "A",
                "analysis": "解析……", "front": "下列属于胶体的是", "back": "A",
            }],
        }],
    }


def main():
    for p in (S3, S2):
        assert p.exists(), f'缺少 schema 文件 {p.name}'
    s3 = json.loads(S3.read_text(encoding='utf-8'))
    s2 = json.loads(S2.read_text(encoding='utf-8'))
    jsonschema.validate(sample_v3(), s3)
    jsonschema.validate(sample_v2(), s2)
    # 3.0 必填字段缺失必须被拒绝
    bad = sample_v3()
    del bad['points'][0]['exam_evidence']
    try:
        jsonschema.validate(bad, s3)
    except jsonschema.ValidationError:
        pass
    else:
        raise AssertionError('3.0 schema 未拒绝缺少 exam_evidence 的点')
    print('schema ok: 3.0 样本通过、2.0 样本通过、缺必填被拒')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAIL: {type(e).__name__}: {e}')
        sys.exit(1)
