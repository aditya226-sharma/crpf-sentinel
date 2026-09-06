"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import coseBilkent from "cytoscape-cose-bilkent";

cytoscape.use(coseBilkent);

import { Activity, Boxes, Fingerprint, GitBranch, MessageSquareText, Search, Send, Spline, Users } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { graphService, logService, queryService } from "@/services";
import type { GraphNodeItem, GraphRelationships, QueryResult } from "@/types";
import { cn } from "@/lib/utils";
import { generateLocalNarrative, type LocalNarrativeEvent } from "@/lib/localNarrative";

const NODE_COLORS: Record<string, string> = {
  case: "#f59e0b",
  person: "#38bdf8",
  phone: "#a78bfa",
  email: "#34d399",
  vehicle: "#f472b6",
  bank_account: "#facc15",
  location: "#4ade80",
};

interface GraphData {
  nodes: Map<string, GraphNodeItem>;
  edges: { source: string; target: string; relation: string; weight: number }[];
}

function mergeInto(data: GraphData, rel: GraphRelationships) {
  for (const [id, node] of Object.entries(rel.nodes)) data.nodes.set(id, node);
  for (const edge of rel.edges) {
    if (!data.edges.some((e) => e.source === edge.source && e.target === edge.target && e.relation === edge.relation)) {
      data.edges.push(edge);
    }
  }
}

function toElements(data: GraphData): ElementDefinition[] {
  const nodes: ElementDefinition[] = [...data.nodes.values()].map((n) => ({
    data: {
      id: n.id,
      label: n.name,
      type: n.entity_type,
      color: NODE_COLORS[n.entity_type] ?? "#94a3b8",
    },
  }));
  const edges: ElementDefinition[] = data.edges.map((e, i) => ({
    data: {
      id: `e${i}`,
      source: e.source,
      target: e.target,
    },
  }));
  return [...nodes, ...edges];
}

const EMPTY_NODES: GraphNodeItem[] = [];

export default function CriminalDashboardPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [graphData, setGraphData] = useState<GraphData>({ nodes: new Map(), edges: [] });
  const [selected, setSelected] = useState<GraphNodeItem | null>(null);
  const [selectedRel, setSelectedRel] = useState<GraphRelationships | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<GraphNodeItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [pathA, setPathA] = useState("");
  const [pathB, setPathB] = useState("");
  const [path, setPath] = useState<GraphNodeItem[] | null>(null);
  const [pathBusy, setPathBusy] = useState(false);
  const [expanding, setExpanding] = useState(false);
  const [nlQuery, setNlQuery] = useState("");
  const [nlResult, setNlResult] = useState<QueryResult | null>(null);
  const [nlBusy, setNlBusy] = useState(false);
  const [localAi, setLocalAi] = useState(() => typeof window !== "undefined" && (window.localStorage.getItem("crpf-local-ai") ?? "on") === "on");
  const [localNarr, setLocalNarr] = useState<LocalNarrativeEvent>({ stage: "idle" });
  const [localText, setLocalText] = useState<string | null>(null);

  const overview = useQuery({ queryKey: ["graph", "overview"], queryFn: graphService.overview, refetchInterval: 60000 });
  const central = useQuery({ queryKey: ["graph", "central"], queryFn: () => graphService.central(30), refetchInterval: 60000 });
  const communities = useQuery({ queryKey: ["graph", "communities"], queryFn: () => graphService.communities(8), refetchInterval: 60000 });
  const recentCases = useQuery({
    queryKey: ["logs", "case-records"],
    queryFn: () => logService.list({ category: "case", page_size: 8 }),
    refetchInterval: 60000,
  });

  const centralItems = useMemo(() => central.data?.items ?? EMPTY_NODES, [central.data]);
  const graphEntities = useMemo(
    () => [...graphData.nodes.values()].sort((a, b) => (b.degree ?? 0) - (a.degree ?? 0)),
    [graphData.nodes],
  );

  const expandFrom = useCallback(
    async (node: GraphNodeItem, depth = 1) => {
      setExpanding(true);
      try {
        const rel = await graphService.relationships(node.id, depth);
        setGraphData((prev) => {
          const next: GraphData = { nodes: new Map(prev.nodes), edges: [...prev.edges] };
          mergeInto(next, rel);
          return next;
        });
      } finally {
        setExpanding(false);
      }
    },
    [],
  );

  // Seed the canvas from central hubs + communities so it is populated instantly.
  useEffect(() => {
    let cancelled = false;
    const hubs = centralItems.slice(0, 6).map((n) => n.id);
    const communityIds = (communities.data?.items ?? []).flatMap((c) => c.entities.slice(0, 4).map((e) => e.id));
    const toExpand = [...new Set([...hubs, ...communityIds])].slice(0, 10);
    setExpanding(true);
    Promise.all(toExpand.map((id, i) => graphService.relationships(id, i < 6 ? 1 : 1)))
      .then((results) => {
        if (cancelled) return;
        const next: GraphData = { nodes: new Map(), edges: [] };
        results.forEach((rel) => mergeInto(next, rel));
        const fallbackNodes = [...(communities.data?.items ?? []).flatMap((c) => c.entities)];
        for (const n of fallbackNodes) next.nodes.set(n.id, n);
        setGraphData(next);
      })
      .catch(() => undefined)
      .finally(() => setExpanding(false));
    return () => {
      cancelled = true;
    };
  }, [centralItems, communities.data]);

  // (Re)render cytoscape whenever graph data changes.
  useEffect(() => {
    if (!containerRef.current) return;
    const elements = toElements(graphData);
    if (cyRef.current) {
      cyRef.current.json({ elements });
      const layout = cyRef.current.layout({
        name: "cose-bilkent",
        animate: false,
        fit: true,
        padding: 40,
        quality: "good",
        nodeRepulsion: 9000,
        idealEdgeLength: 100,
        gravity: 0.5,
        numIter: 1000,
      } as unknown as cytoscape.LayoutOptions);
      layout.run();
      return;
    }
    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            label: "data(label)",
            color: "#e2e8f0",
            "font-size": 9,
            "text-valign": "center",
            "text-background-color": "rgba(15,23,42,0.85)",
            "text-background-opacity": 1,
            "text-background-padding": "3px",
            "text-border-color": "data(color)",
            "text-border-opacity": 0.4,
            "text-border-width": 1,
            "text-wrap": "none",
            width: "30px",
            height: "30px",
            "border-width": 1.5,
            "border-color": "#0f172a",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": "#334155",
            "target-arrow-shape": "none",
            "curve-style": "bezier",
            opacity: 0.85,
          },
        },
        {
          selector: "edge.highlighted",
          style: { width: 3, "line-color": "#f59e0b", "target-arrow-color": "#f59e0b", opacity: 1 },
        },
        {
          selector: "node.highlighted",
          style: { "border-width": 3, "border-color": "#f59e0b" },
        },
        {
          selector: "node.selected",
          style: { "border-width": 3, "border-color": "#38bdf8", "border-opacity": 1 },
        },
      ],
      layout: {
        name: "cose-bilkent",
        animate: false,
        fit: true,
        padding: 40,
        quality: "good",
        nodeRepulsion: 9000,
        idealEdgeLength: 100,
        gravity: 0.5,
        numIter: 1000,
      } as unknown as cytoscape.LayoutOptions,
      wheelSensitivity: 0.2,
    });
    cyRef.current.on("tap", "node", (evt) => {
      const nodeId = evt.target.id();
      void selectNode(nodeId);
    });
    return () => {
      cyRef.current?.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphData]);

  const selectNode = useCallback(async (nodeId: string) => {
    const node = graphData.nodes.get(nodeId) ?? null;
    setSelected(node);
    if (!node) return;
    const rel = await graphService.relationships(nodeId, 1);
    setSelectedRel(rel);
    if (cyRef.current) {
      cyRef.current.$("node.selected").removeClass("selected");
      cyRef.current.$(`#${CSS.escape(nodeId)}`).addClass("selected");
    }
  }, [graphData.nodes]);

  const runSearch = useCallback(async (term: string) => {
    if (!term.trim()) {
      setSearchResults([]);
      return;
    }
    setSearching(true);
    try {
      const res = await graphService.search(term, 12);
      setSearchResults(res.items);
    } finally {
      setSearching(false);
    }
  }, []);

  const runQuery = useCallback(async () => {
    const localBusy =
      localNarr.stage === "downloading" || localNarr.stage === "loading" || localNarr.stage === "generating";
    if (!nlQuery.trim() || nlBusy || localBusy) return;
    setNlBusy(true);
    setNlResult(null);
    setLocalNarr({ stage: "idle" });
    setLocalText(null);
    try {
      const res = await queryService.run(nlQuery);
      setNlResult(res);
      if (!res.narrative) setLocalNarr({ stage: "idle" });
      if (localAi && !res.narrative && res.results.length > 0) {
        const narrative = await generateLocalNarrative(res, (event) => setLocalNarr(event));
        if (narrative) setLocalText(narrative);
      }
    } catch {
      setNlResult(null);
    } finally {
      setNlBusy(false);
    }
  }, [nlQuery, localAi, nlBusy, localNarr.stage]);

  const runPath = useCallback(async () => {
    if (!pathA || !pathB) return;
    setPathBusy(true);
    setPath(null);
    try {
      const res = await graphService.connectivity(pathA, pathB);
      setPath(res.path);
      if (cyRef.current) {
        const cy = cyRef.current;
        cy.elements().removeClass("highlighted");
        const ids = res.path.map((n) => n.id);
        ids.forEach((id) => {
          cy.$(`#${CSS.escape(id)}`).addClass("highlighted");
        });
        res.path.slice(0, -1).forEach((n, i) => {
          const next = res.path[i + 1];
          cy.edges(`[source="${n.id}"][target="${next.id}"]`).addClass("highlighted");
          cy.edges(`[source="${next.id}"][target="${n.id}"]`).addClass("highlighted");
        });
      }
    } catch {
      setPath([]);
    } finally {
      setPathBusy(false);
    }
  }, [pathA, pathB]);

  const entityTypeBadges = Object.entries(overview.data?.entity_types ?? {});
  const lastPathIds = useMemo(() => new Set((path ?? []).map((n) => n.id)), [path]);
  const localBusy =
    localNarr.stage === "downloading" || localNarr.stage === "loading" || localNarr.stage === "generating";

  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-foreground">Criminal Intelligence</h1>
            <p className="text-sm text-muted">
              Entity-relationship graph over synthetic case records. All names, numbers and
              records are fabricated demo data.
            </p>
          </div>
          <Badge variant="medium">{overview.data?.backend ?? "relational"} graph store</Badge>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {[
          { label: "Graph Nodes", value: overview.data?.nodes ?? 0, icon: Fingerprint },
          { label: "Relationships", value: overview.data?.edges ?? 0, icon: GitBranch },
          { label: "Hub Entities", value: centralItems.length, icon: Users },
          { label: "Communities", value: communities.data?.items.length ?? 0, icon: Boxes },
          { label: "Recent Records", value: recentCases.data?.meta.total ?? 0, icon: Spline },
        ].map((item) => (
          <Card key={item.label}>
            <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-xs font-medium text-muted">{item.label}</CardTitle>
              <item.icon className="h-4 w-4 text-accent" />
            </CardHeader>
            <CardContent>
              <div className="font-mono text-2xl font-semibold text-foreground">{item.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.6fr_1fr]">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle>Network Map</CardTitle>
              <CardDescription>Tap a node to inspect its relationships</CardDescription>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(NODE_COLORS).map(([type, color]) => (
                <span key={type} className="inline-flex items-center gap-1 text-[10px] text-muted">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                  {type}
                </span>
              ))}
            </div>
          </CardHeader>
          <CardContent>
            <div className="mb-3 flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted" />
                <Input
                  className="pl-8"
                  placeholder="Search entities… (person, phone, vehicle, case)"
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    void runSearch(e.target.value);
                  }}
                />
                {searchResults.length > 0 && (
                  <div className="absolute z-20 mt-1 w-full rounded-md border border-border bg-surface shadow-lg">
                    {searchResults.slice(0, 6).map((r) => (
                      <button
                        key={r.id}
                        type="button"
                        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs text-foreground hover:bg-surface2"
                        onClick={() => {
                          void expandFrom(r, 1);
                          void selectNode(r.id);
                          setSearchTerm(r.name);
                          setSearchResults([]);
                        }}
                      >
                        <span className="truncate">{r.name}</span>
                        <Badge variant="default">{r.entity_type}</Badge>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <Button variant="outline" size="sm" disabled={expanding} onClick={() => setGraphData({ nodes: new Map(), edges: [] })}>
                Reset
              </Button>
            </div>

            <div
              ref={containerRef}
              className="h-[460px] w-full overflow-hidden rounded-md border border-border bg-background"
              aria-label="Criminal intelligence graph"
            />
            <p className="mt-2 text-xs text-muted">
              {graphData.nodes.size} nodes · {graphData.edges.length} edges visible
              {expanding && <span className="ml-2 text-accent">expanding…</span>}
            </p>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader className="space-y-0 pb-2">
              <CardTitle>Hidden Nexus Path</CardTitle>
              <CardDescription>Shortest path between any two entities</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <select
                  className="w-full rounded-md border border-border bg-surface2 px-2.5 py-2 text-xs text-foreground"
                  value={pathA}
                  onChange={(e) => setPathA(e.target.value)}
                >
                  <option value="">From…</option>
                  {graphEntities.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name} ({n.entity_type})
                    </option>
                  ))}
                </select>
                <select
                  className="w-full rounded-md border border-border bg-surface2 px-2.5 py-2 text-xs text-foreground"
                  value={pathB}
                  onChange={(e) => setPathB(e.target.value)}
                >
                  <option value="">To…</option>
                  {graphEntities.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name} ({n.entity_type})
                    </option>
                  ))}
                </select>
                <Button size="sm" className="w-full" disabled={!pathA || !pathB || pathBusy} onClick={() => void runPath()}>
                  Find Path
                </Button>
              </div>
              {path && path.length > 0 && (
                <ol className="mt-3 space-y-1.5 rounded-md border border-accent/30 bg-accent/5 p-3">
                  {path.map((n, i) => (
                    <li key={`${n.id}-${i}`} className="flex items-center gap-1.5 text-[11px]">
                      <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: NODE_COLORS[n.entity_type] }} />
                      <span className={cn("truncate", lastPathIds.has(n.id) && "font-semibold text-accent")}>
                        {n.name}
                      </span>
                      <span className="ml-auto shrink-0 text-muted">{n.entity_type}</span>
                    </li>
                  ))}
                  <li className="pt-1 text-[10px] text-accent">Path found — {path.length - 1} hops</li>
                </ol>
              )}
              {path && path.length === 0 && (
                <p className="mt-3 text-[11px] text-muted">No path between the selected entities.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="space-y-0 pb-2">
              <CardTitle>Ask the Corpus</CardTitle>
              <CardDescription>Template-based query over alerts, logons and flows</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <MessageSquareText className="absolute left-2.5 top-2.5 h-4 w-4 text-muted" />
                  <Input
                    className="pl-8"
                    placeholder={'e.g. "open high alerts", "failed logons by rpatil", "network scan"'}
                    value={nlQuery}
                    onChange={(e) => setNlQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void runQuery();
                    }}
                  />
                </div>
                <Button size="sm" disabled={!nlQuery.trim() || nlBusy || localBusy} onClick={() => void runQuery()}>
                  <Send className="h-3.5 w-3.5" />
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-2 pb-1">
                <label className="flex cursor-pointer items-center gap-1.5 text-[10px] text-muted">
                  <input
                    type="checkbox"
                    className="h-3 w-3 accent-current"
                    checked={localAi}
                    onChange={(e) => {
                      setLocalAi(e.target.checked);
                      try {
                        window.localStorage.setItem("crpf-local-ai", e.target.checked ? "on" : "off");
                      } catch {
                        /* ignore storage errors */
                      }
                    }}
                  />
                  Free in-browser AI summary
                </label>
                <span className="text-[10px] text-muted">· runs on your device — no key, no cost</span>
                {(localNarr.stage === "downloading" || localNarr.stage === "loading" || localNarr.stage === "generating") && (
                  <span className="ml-auto animate-pulse text-[10px] text-accent">
                    {localNarr.detail ?? `local AI ${localNarr.stage}…`}
                  </span>
                )}
                {localNarr.stage === "error" && (
                  <span className="ml-auto text-[10px] text-muted">in-browser AI unavailable — template answer shown</span>
                )}
              </div>
              {nlBusy && !nlResult && <Skeleton className="h-16 w-full" />}
              {nlResult && (
                <div className="rounded-md border border-border p-3">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="text-[11px] font-semibold text-foreground">{nlResult.template}</span>
                    <Badge variant={nlResult.confidence === "high" ? "default" : "outline"}>
                      {nlResult.confidence} confidence
                    </Badge>
                  </div>
                  <p className="mb-2 text-[10px] text-muted">{nlResult.explanation}</p>
                  {nlResult.narrative && !localText && (
                    <p className="mb-2 rounded-md border border-accent/30 bg-accent/5 p-2 text-[11px] leading-snug text-foreground">
                      {nlResult.narrative}
                    </p>
                  )}
                  {localText && (
                    <p className="mb-2 rounded-md border border-accent/30 bg-accent/5 p-2 text-[11px] leading-snug text-foreground">
                      <span className="mb-1 inline-flex items-center gap-1.5">
                        <Badge variant="outline">in-browser · free</Badge>
                      </span>
                      <span className="block">{localText}</span>
                    </p>
                  )}
                  {nlResult.results.length === 0 && <p className="text-[10px] text-muted">No rows matched — no fabricated answers.</p>}
                  <ul className="max-h-40 space-y-1 overflow-y-auto">
                    {nlResult.results.map((r, i) => (
                      <li key={i} className="text-[11px] leading-snug">
                        <span className="font-medium text-foreground">{r.label}</span>
                        <span className="block text-[10px] text-muted">{r.detail}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="space-y-0 pb-2">
              <CardTitle>{selected ? "Selected Entity" : "Central Entities"}</CardTitle>
              <CardDescription>
                {selected ? "Relationships attached to this entity" : "Highest-connectivity hubs"}
              </CardDescription>
            </CardHeader>
            <CardContent className="max-h-72 space-y-1.5 overflow-y-auto">
              {selected && selectedRel ? (
                <>
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: NODE_COLORS[selected.entity_type] }} />
                    <span className="text-xs font-medium text-foreground">{selected.name}</span>
                    <Badge variant="default">{selected.entity_type}</Badge>
                  </div>
                  {selectedRel.edges.length === 0 && <p className="text-[11px] text-muted">No direct relationships.</p>}
                  {selectedRel.edges.slice(0, 12).map((e, i) => {
                    const otherId = e.source === selected.id ? e.target : e.source;
                    const other = selectedRel.nodes[otherId];
                    return (
                      <button
                        key={i}
                        type="button"
                        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[11px] hover:bg-surface2"
                        onClick={() => void selectNode(otherId)}
                      >
                        <span
                          className="h-2 w-2 shrink-0 rounded-full"
                          style={{ backgroundColor: NODE_COLORS[other?.entity_type ?? ""] ?? "#94a3b8" }}
                        />
                        <span className="truncate text-foreground">{other?.name ?? otherId}</span>
                        <span className="ml-auto shrink-0 text-muted">{e.relation}</span>
                      </button>
                    );
                  })}
                  <Button variant="ghost" size="sm" className="w-full" onClick={() => void expandFrom(selected, 1)}>
                    Expand neighborhood
                  </Button>
                </>
              ) : selected ? (
                <p className="text-[11px] text-muted">Loading relationships…</p>
              ) : (
                centralItems.slice(0, 12).map((n) => (
                  <button
                    key={n.id}
                    type="button"
                    className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[11px] hover:bg-surface2"
                    onClick={() => void expandFrom(n, 1)}
                  >
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: NODE_COLORS[n.entity_type] }} />
                    <span className="truncate text-foreground">{n.name}</span>
                    <span className="ml-auto shrink-0 text-muted">{n.degree} links</span>
                  </button>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader className="space-y-0 pb-2">
            <CardTitle>Detected Communities</CardTitle>
            <CardDescription>Connected components in the case corpus</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {communities.isLoading && <Skeleton className="h-24 w-full" />}
            {communities.data?.items.map((c) => (
              <div key={c.id} className="rounded-md border border-border p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-foreground">Component · {c.entities.length} entities</span>
                  <Badge variant="default">{c.id.slice(0, 8)}</Badge>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {c.entities.slice(0, 20).map((e) => (
                    <button
                      key={e.id}
                      type="button"
                      className="inline-flex items-center gap-1 rounded-full border border-border bg-surface2 px-2 py-0.5 text-[10px] text-foreground hover:border-accent/50"
                      onClick={() => void selectNode(e.id)}
                    >
                      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: NODE_COLORS[e.entity_type] }} />
                      {e.name}
                    </button>
                  ))}
                  {c.entities.length > 20 && <span className="text-[10px] text-muted">+{c.entities.length - 20}</span>}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="space-y-0 pb-2">
            <CardTitle>Recent Case Records</CardTitle>
            <CardDescription>Latest synthetic records through the parser pipeline</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {recentCases.isLoading && <Skeleton className="h-24 w-full" />}
            {(recentCases.data?.items ?? []).map((e) => (
              <div key={e.id} className="flex items-center gap-3 rounded-md border border-border px-3 py-2">
                <Activity className="h-3.5 w-3.5 shrink-0 text-accent" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[11px] font-medium text-foreground">{e.command_line ?? "case record"}</p>
                  <p className="text-[10px] text-muted">
                    {e.hostname ?? "unit"} · {new Date(e.timestamp).toLocaleString()}
                  </p>
                </div>
                <Badge variant="default">{e.action}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {entityTypeBadges.length > 0 && (
        <Card>
          <CardHeader className="space-y-0 pb-2">
            <CardTitle>Entity Distribution</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {entityTypeBadges.map(([type, count]) => (
              <span key={type} className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-[11px] text-foreground">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: NODE_COLORS[type] ?? "#94a3b8" }} />
                {type}
                <span className="text-muted">{count}</span>
              </span>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}