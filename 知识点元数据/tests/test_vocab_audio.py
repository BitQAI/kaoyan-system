#!/usr/bin/env python3
"""按卡片生成音频脚本与 mp3（词 / 释义 / 例句 / 整卡、段落）。"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'audio_mod', ROOT / '知识点元数据/scripts/vocab_audio.py')
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)

WORD_CARD = {
    "card_id": "c2041001-1", "kind": "词汇",
    "payload": {"type": "word", "word": "momentum",
                "meanings": [{"pos": "n.", "cn": "势头；推动力"}],
                "examples": [{"kind": "真题", "quote": "The move picked up momentum."},
                             {"kind": "例句", "quote": "The campaign gained momentum."}]},
}
PHRASE_CARD = {
    "card_id": "c2041101-1", "kind": "词汇",
    "payload": {"type": "phrase", "word": "account for",
                "meanings": [{"pos": "phr.", "cn": "占比"}]},
}
ESSAY_CARD = {
    "card_id": "c2040805-2", "kind": "回译",
    "answer": "Dear David, I am writing to suggest that you go to the art exhibition.",
    "payload": {},
}


def main():
    clips = a.scripts_for(WORD_CARD)
    names = [c['clip'] for c in clips]
    assert names == ['word', 'meaning', 'sentence'], names
    assert clips[0]['lang'] == 'en-US' and clips[1]['lang'] == 'zh-CN'
    assert clips[1]['text'] == '势头；推动力'
    assert clips[2]['text'].startswith('The move picked up')

    phrase = a.scripts_for(PHRASE_CARD)
    assert [c['clip'] for c in phrase] == ['word', 'meaning']
    assert phrase[0]['text'] == 'account for'

    essay = a.scripts_for(ESSAY_CARD)
    assert [c['clip'] for c in essay] == ['para']
    assert essay[0]['lang'] == 'en-US'

    # 文件名规则
    assert a.clip_path('204', 'c2041001-1', 'word').name == 'c2041001-1-word.mp3'
    assert a.clip_path('204', 'c2041001-1', None).name == 'c2041001-1.mp3'
    print('vocab audio ok')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FAIL: {type(exc).__name__}: {exc}')
        sys.exit(1)
