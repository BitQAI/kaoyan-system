"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { getJson, getToken, postJson } from "@/lib/api";

type Kind = "point" | "card";
interface IdMap { point: string[]; card: string[] }

interface Ctx {
  ids: IdMap;
  has: (kind: Kind, id: string) => boolean;
  toggle: (kind: Kind, id: string) => void;
}

const C = createContext<Ctx>({ ids: { point: [], card: [] }, has: () => false, toggle: () => {} });
export const useFavorites = () => useContext(C);

export function FavoritesProvider({ children }: { children: React.ReactNode }) {
  const [ids, setIds] = useState<IdMap>({ point: [], card: [] });

  useEffect(() => {
    // 登录页没有令牌，先别请求，免得 401 把刚填的状态清掉
    if (!getToken()) return;
    getJson<{ ids: IdMap }>("/api/favorites")
      .then((d) => setIds(d.ids ?? { point: [], card: [] }))
      .catch(() => {});
  }, []);

  const toggle = useCallback((kind: Kind, id: string) => {
    const on = !(ids[kind] ?? []).includes(id);
    // 先本地翻转，请求失败再回滚
    setIds((prev) => ({
      ...prev,
      [kind]: on ? [id, ...prev[kind]] : prev[kind].filter((x) => x !== id),
    }));
    postJson<{ ids: IdMap }>("/api/favorites", { kind, ref_id: id, on })
      .then((d) => setIds(d.ids))
      .catch(() => {
        setIds((prev) => ({
          ...prev,
          [kind]: on ? prev[kind].filter((x) => x !== id) : [id, ...prev[kind]],
        }));
      });
  }, [ids]);

  const has = useCallback(
    (kind: Kind, id: string) => (ids[kind] ?? []).includes(id), [ids]);
  const value = useMemo(() => ({ ids, has, toggle }), [ids, has, toggle]);

  return <C.Provider value={value}>{children}</C.Provider>;
}
