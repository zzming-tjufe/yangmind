import { useEffect, useMemo, useState } from "react";
import {
  getSiteContent,
  getSitePages,
  type SiteContent,
  type SitePage,
} from "../api/admin";

export function useSitePages() {
  const [pages, setPages] = useState<SitePage[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getSitePages()
      .then((rows) => {
        if (!cancelled) setPages(rows);
      })
      .catch(() => {
        if (!cancelled) setPages([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const byKey = useMemo(() => {
    const map: Record<string, SitePage> = {};
    pages.forEach((p) => {
      map[p.page_key] = p;
    });
    return map;
  }, [pages]);

  return { pages, byKey, loading };
}

export function useSiteContent() {
  const [blocks, setBlocks] = useState<SiteContent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getSiteContent()
      .then((rows) => {
        if (!cancelled) setBlocks(rows);
      })
      .catch(() => {
        if (!cancelled) setBlocks([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const byKey = useMemo(() => {
    const map: Record<string, SiteContent> = {};
    blocks.forEach((b) => {
      map[b.block_key] = b;
    });
    return map;
  }, [blocks]);

  return { blocks, byKey, loading };
}
