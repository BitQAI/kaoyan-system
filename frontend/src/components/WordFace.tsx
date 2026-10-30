"use client";
import { loadClip } from "@/lib/listen";
import type { Card, WordExample, WordPayload } from "@/lib/types";

let player: HTMLAudioElement | null = null;

/** 分片音频；缺失或播放失败时回退浏览器语音，保证按钮永远有反应 */
function play(cardId: string, clip: string, text: string, lang: string) {
  let fellBack = false;
  const speak = () => {
    if (fellBack) return;
    fellBack = true;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang;
      u.rate = 0.92;
      window.speechSynthesis.speak(u);
    } catch { /* 浏览器不支持就静默 */ }
  };
  loadClip(cardId, clip)
    .then((url) => {
      player?.pause();
      player = player ?? new Audio();
      player.src = url;
      player.onerror = speak;
      return player.play();
    })
    .catch(speak);
}

function Speaker({ onClick, title }: { onClick: () => void; title: string }) {
  return (
    <button className="word-speaker" title={title} aria-label={title}
      onClick={(e) => { e.stopPropagation(); onClick(); }}>🔊</button>
  );
}

/** 把例句里的目标词标出来；找不到就原样显示 */
export function Quote({ text, word }: { text: string; word?: string }) {
  if (!word) return <>{text}</>;
  const i = text.toLowerCase().indexOf(word.toLowerCase());
  if (i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <mark>{text.slice(i, i + word.length)}</mark>
      {text.slice(i + word.length)}
    </>
  );
}

function Example({ ex, cardId, word, audioClip }:
  { ex: WordExample; cardId: string; word?: string; audioClip?: string }) {
  const real = ex.kind === "真题";
  const where = [ex.year, ex.part, ex.text, ex.qno ? `第 ${ex.qno} 题` : ""]
    .filter(Boolean).join(" · ");
  return (
    <div className={`word-ex${real ? "" : " note"}`}>
      <blockquote className="word-quote">
        <Quote text={ex.quote} word={word} />
        {ex.cn && <span className="cn">{ex.cn}</span>}
      </blockquote>
      <div className="word-meta">
        {where && <span>{where}</span>}
        {audioClip && (
          <button className="btn small" onClick={(e) => {
            e.stopPropagation();
            play(cardId, audioClip, ex.quote, "en-US");
          }}>🔊 读原句</button>
        )}
      </div>
      {ex.tested && <div className="word-tested">考法：{ex.tested}</div>}
    </div>
  );
}

function Confusable({ p }: { p: WordPayload }) {
  return (
    <>
      <div className="block">
        <h4>选词填空</h4>
        <div className="word-stem">
          {p.stem?.split("____").map((t, i, arr) => (
            <span key={i}>{t}{i < arr.length - 1 && <u>&nbsp;&nbsp;&nbsp;&nbsp;</u>}</span>
          ))}
        </div>
        <div className="word-group">{p.group?.map((g) => (
          <span key={g} className={`word-chip${g === p.answer ? " ok" : ""}`}>{g}</span>
        ))}</div>
      </div>
      <div className="block">
        <h4>答案与辨析</h4>
        <div className="word-stem"><b>{p.answer}</b></div>
        {p.diff && <div className="word-tested">{p.diff}</div>}
      </div>
    </>
  );
}

export default function WordFace({ card, side }:
  { card: Card; side: "front" | "back" }) {
  const p = card.payload as WordPayload | undefined;
  if (!p || !p.type) return null;
  const word = p.word ?? "";
  const pos = p.meanings?.[0]?.pos ?? "";

  if (p.type === "confusable") {
    if (side === "front") {
      return (
        <div className="word-face">
          <div className="block">
            <h4>选词填空</h4>
            <div className="word-stem">
              {p.stem?.split("____").map((t, i, arr) => (
                <span key={i}>{t}{i < arr.length - 1 && <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>}</span>
              ))}
            </div>
            <div className="word-group">{p.group?.map((g) => (
              <span key={g} className="word-chip">{g}</span>
            ))}</div>
          </div>
        </div>
      );
    }
    return <div className="word-face"><Confusable p={p} /></div>;
  }

  if (side === "front") {
    return (
      <div className="word-face">
        <div className="word-head">
          <div>
            <div className="word-title">{word}</div>
            <div className="word-phonetic">
              {p.phonetic}{p.phonetic && pos ? " · " : ""}{pos}
            </div>
          </div>
          <span className="word-gap" />
          <Speaker title="读单词" onClick={() => play(card.card_id, "word", word, "en-US")} />
        </div>
        <div className="word-hint">点击卡片或按空格翻面</div>
      </div>
    );
  }

  return (
    <div className="word-face">
      <div className="block">
        <h4>释义</h4>
        <ul className="word-senses">
          {(p.meanings ?? []).map((m, i) => (
            <li key={i}><span className="pos">{m.pos}</span>{m.cn}</li>
          ))}
        </ul>
      </div>

      {(p.examples ?? []).map((ex, i) => (
        <div className="block" key={i}>
          <h4>
            真题情境
            <span className={`word-badge ${ex.kind === "真题" ? "real" : "note"}`}>
              {ex.kind === "真题" ? "真题" : ex.note ?? "例句（非真题原句）"}
            </span>
          </h4>
          <Example ex={ex} cardId={card.card_id} word={word}
            audioClip={i === 0 ? "sentence" : undefined} />
        </div>
      ))}

      {!!p.confusables?.length && (
        <div className="block">
          <h4>易混 / 近义</h4>
          <div className="word-confuse">
            {p.confusables.map((c) => (
              <div className="row" key={c.word}><b>{c.word}</b><span>{c.diff}</span></div>
            ))}
          </div>
        </div>
      )}

      {!!p.phrases?.length && (
        <div className="block">
          <h4>词组</h4>
          <div className="word-confuse">
            {p.phrases.map((ph) => (
              <div className="row" key={ph.en}><b>{ph.en}</b><span>{ph.cn}</span></div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
