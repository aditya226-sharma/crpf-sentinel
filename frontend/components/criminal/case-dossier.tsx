"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import {
  Camera,
  File as FileIcon,
  FileText,
  Film,
  FolderPlus,
  Printer,
  ShieldAlert,
  Upload,
  Languages,
  Download,
  Phone,
  Receipt,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { caseIntakeService } from "@/services";
import type { CaseDocument, CaseIntakeItem, CaseReport, ReportLanguage } from "@/types";

const KINDS: Record<string, { label: string; icon: typeof FileIcon }> = {
  photo: { label: "Photo", icon: Camera },
  fir: { label: "FIR", icon: FileText },
  call_records: { label: "Call records", icon: Phone },
  forensic: { label: "Forensic", icon: ShieldAlert },
  cctv: { label: "CCTV", icon: Film },
  document: { label: "Document", icon: FileIcon },
};

const LANGS: { value: ReportLanguage; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिंदी" },
  { value: "hinglish", label: "Hinglish" },
];

function formatSize(size: number): string {
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  if (size >= 1024) return `${Math.round(size / 1024)} KB`;
  return `${size} B`;
}

function guessKind(filename: string): string {
  const lower = filename.toLowerCase();
  const ext = lower.split(".").pop() ?? "";
  if (/(cctv|camera|video)/.test(lower) || ["mp4", "avi", "mkv", "mov", "webm", "m4v", "3gp"].includes(ext)) return "cctv";
  if (/fir|first information|complaint/.test(lower)) return "fir";
  if (/call|cdr|voice|detail/.test(lower)) return "call_records";
  if (/forensic|fss/.test(lower)) return "forensic";
  if (["jpg", "jpeg", "png", "gif", "webp", "bmp", "heic"].includes(ext)) return "photo";
  return "document";
}

export function CaseDossier() {
  const [cases, setCases] = useState<CaseIntakeItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseIntakeItem | null>(null);
  const [listBusy, setListBusy] = useState(false);

  const [title, setTitle] = useState("");
  const [fir, setFir] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const browseRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  const [lang, setLang] = useState<ReportLanguage>("en");
  const [report, setReport] = useState<CaseReport | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshList = useCallback(async () => {
    setListBusy(true);
    try {
      const items = await caseIntakeService.list();
      setCases(items);
      setSelectedId(items[0]?.id ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load cases");
    } finally {
      setListBusy(false);
    }
  }, []);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setReport(null);
      return;
    }
    let cancelled = false;
    setReport(null);
    caseIntakeService
      .detail(selectedId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const selectedCase = useMemo(
    () => cases.find((c) => c.id === selectedId) ?? detail,
    [cases, selectedId, detail],
  );
  const displayDoc: CaseDocument[] = useMemo(
    () => detail?.documents ?? selectedCase?.documents ?? [],
    [detail, selectedCase],
  );

  const createCase = async () => {
    if (!title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const created = await caseIntakeService.create(title.trim(), fir.trim(), description.trim());
      setTitle("");
      setFir("");
      setDescription("");
      await refreshList();
      setSelectedId(created.id);
      setNotice(`Case ${created.case_id} created — now upload evidence.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create case");
    } finally {
      setCreating(false);
    }
  };

  const uploadFiles = async () => {
    if (!selectedId || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      const res = await caseIntakeService.upload(selectedId, files);
      setNotice(`${res.accepted} file(s) uploaded (${res.skipped} skipped).`);
      setFiles([]);
      const d = await caseIntakeService.detail(selectedId);
      setDetail(d);
      await refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const generateReport = async (selected: CaseIntakeItem) => {
    setReportBusy(true);
    setError(null);
    try {
      const data = await caseIntakeService.report(selected.case_id, lang);
      setReport(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Report generation failed");
    } finally {
      setReportBusy(false);
    }
  };

  const downloadPdf = async () => {
    if (!selectedCase) return;
    setPdfBusy(true);
    setError(null);
    try {
      const blob = await caseIntakeService.reportPdf(selectedCase.case_id, lang);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `cyberrakshak-${selectedCase.case_id}-${lang}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
      setNotice(`PDF downloaded in ${LANGS.find((l) => l.value === lang)?.label}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "PDF download failed");
    } finally {
      setPdfBusy(false);
    }
  };

  const kindBadge = (kind: string) => {
    const meta = KINDS[kind] ?? KINDS.document;
    const Icon = meta.icon;
    return (
      <span className="inline-flex items-center gap-1">
        <Icon className="h-3 w-3 text-muted" />
        {meta.label}
      </span>
    );
  };

  const addFiles = (incoming: FileList | File[]) => {
    setFiles((prev) => [...prev, ...Array.from(incoming)]);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!e.dataTransfer.files || e.dataTransfer.files.length === 0) return;
    addFiles(e.dataTransfer.files);
  };

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Receipt className="h-4 w-4 text-accent" />
            Crime Case Dossier & Report
          </CardTitle>
          <CardDescription>
            Upload case evidence (FIR, photos, call records, forensic reports, CCTV clips…) and
            generate a downloadable PDF report in English, Hindi or Hinglish.
          </CardDescription>
        </div>
        <Badge variant="outline">{LANGUAGES_JOINED}</Badge>
      </CardHeader>
      <CardContent className="space-y-5">
        {error && (
          <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-[11px] text-red-400">
            {error}
          </p>
        )}
        {notice && (
          <p className="rounded-md border border-emerald-900/40 bg-emerald-950/30 px-3 py-2 text-[11px] text-emerald-400">
            {notice}
          </p>
        )}

        <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
          <div className="space-y-3">
            <div className="rounded-md border border-border p-3">
              <div className="mb-2 text-[11px] font-semibold text-foreground">New case</div>
              <Input placeholder="Case title (e.g. Market theft probe)" value={title} onChange={(e) => setTitle(e.target.value)} className="mb-2" />
              <Input placeholder="FIR number (e.g. 0123/2026)" value={fir} onChange={(e) => setFir(e.target.value)} className="mb-2" />
              <Textarea placeholder="Case notes / description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="mb-2" />
              <Button size="sm" className="w-full" disabled={!title.trim() || creating} onClick={() => void createCase()}>
                <FolderPlus className="h-3.5 w-3.5" /> Create case
              </Button>
            </div>

            <div className="rounded-md border border-border p-3">
              <div className="mb-2 text-[11px] font-semibold text-foreground">Cases</div>
              {listBusy && cases.length === 0 && <Skeleton className="h-16 w-full" />}
              {cases.length === 0 && !listBusy && <p className="text-[11px] text-muted">No cases yet — create one to begin.</p>}
              <div className="max-h-44 space-y-1 overflow-y-auto">
                {cases.map((c) => {
                  const counts = c.doc_counts ?? {};
                  const total = Object.values(counts).reduce((a, b) => a + (b ?? 0), 0);
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => setSelectedId(c.id)}
                      className={cn(
                        "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-[11px] hover:bg-surface2",
                        selectedId === c.id && "bg-surface2",
                      )}
                    >
                      <span className="truncate font-medium text-foreground">{c.title}</span>
                      <span className="ml-2 shrink-0 text-muted">{c.case_id}</span>
                      <Badge variant="outline" className="ml-2 shrink-0">{total} files</Badge>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <div className="rounded-md border border-border p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <span className="text-[11px] font-semibold text-foreground">
                  Evidence — {selectedCase?.case_id ?? "select a case"}
                </span>
                {selectedCase && <Badge variant="default">{selectedCase.status}</Badge>}
              </div>
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={cn(
                  "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border border-dashed px-3 py-5 text-[11px] text-muted hover:border-accent/50",
                  dragging ? "border-accent bg-accent/10" : "border-border bg-surface2",
                )}
              >
                <Upload className="h-5 w-5" />
                <span className="text-center">
                  Drag &amp; drop case evidence here, or add them below — photos, FIR, CDR, forensic, CCTV, …
                </span>
                <span className="flex flex-wrap items-center justify-center gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => browseRef.current?.click()}>
                    Browse files
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => folderRef.current?.click()}>
                    Choose folder
                  </Button>
                </span>
                <input
                  ref={browseRef}
                  type="file"
                  multiple
                  className="hidden"
                  accept="*/*"
                  onChange={(e) => {
                    if (e.target.files) addFiles(e.target.files);
                    e.target.value = "";
                  }}
                />
                <input
                  ref={folderRef}
                  type="file"
                  multiple
                  className="hidden"
                  {...({ webkitdirectory: "" } as Record<string, unknown>)}
                  onChange={(e) => {
                    if (e.target.files) addFiles(e.target.files);
                    e.target.value = "";
                  }}
                />
              </div>
              {files.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {files.map((f, i) => (
                    <span key={i} className="inline-flex items-center gap-1 rounded-full border border-border bg-surface2 px-2 py-0.5 text-[10px] text-foreground">
                      {kindBadge(guessKind(f.name))}
                      <span className="max-w-[140px] truncate">{f.name}</span>
                      <span className="text-muted">{formatSize(f.size)}</span>
                    </span>
                  ))}
                </div>
              )}
              <div className="mt-2 flex gap-2">
                <Button size="sm" className="w-full" disabled={!selectedId || files.length === 0 || uploading} onClick={() => void uploadFiles()}>
                  <Upload className="h-3.5 w-3.5" /> {uploading ? "Uploading…" : "Upload evidence"}
                </Button>
              </div>
              <div className="mt-3 space-y-1">
                {displayDoc.length === 0 && <p className="text-[10px] text-muted">No evidence uploaded yet.</p>}
                {displayDoc.map((d) => (
                  <div key={d.id} className="flex items-center gap-2 rounded-md border border-border px-2 py-1.5 text-[11px]">
                    {kindBadge(d.kind)}
                    <span className="min-w-0 flex-1 truncate text-foreground">{d.filename}</span>
                    <span className="shrink-0 text-muted">{formatSize(d.size)}</span>
                    {d.available ? (
                      <Badge variant="outline">ok</Badge>
                    ) : (
                      <Badge variant="outline" className="text-muted">gone</Badge>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {selectedCase && (
          <div className="rounded-md border border-border p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">{selectedCase.title}</p>
                <p className="text-[10px] text-muted">
                  {selectedCase.case_id} · {selectedCase.fir_number ?? "no FIR no."}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Languages className="h-3.5 w-3.5 text-muted" />
                {LANGS.map((l) => (
                  <Button
                    key={l.value}
                    size="sm"
                    variant={lang === l.value ? "default" : "outline"}
                    onClick={() => setLang(l.value)}
                  >
                    {l.label}
                  </Button>
                ))}
                <Button size="sm" disabled={reportBusy} onClick={() => void generateReport(selectedCase)}>
                  <Printer className="h-3.5 w-3.5" /> {reportBusy ? "Generating…" : "Generate report"}
                </Button>
                <Button size="sm" variant="outline" disabled={!report || pdfBusy} onClick={() => void downloadPdf()}>
                  <Download className="h-3.5 w-3.5" /> {pdfBusy ? "Preparing…" : "Download PDF"}
                </Button>
              </div>
            </div>

            {reportBusy && <Skeleton className="h-40 w-full" />}
            {report && !reportBusy && (
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted">
                  <Badge variant="default">{report.language_label}</Badge>
                  <span>{report.stats.total} evidence items · {report.intel.phones.length} phones extracted</span>
                  {report.cdr && report.cdr.rows > 0 && (
                    <span>· {report.cdr.rows} calls, {report.cdr.top[0]?.number ?? "—"} top contact</span>
                  )}
                </div>
                <iframe
                  title="Crime case report"
                  sandbox=""
                  srcDoc={report.html}
                  className="h-[480px] w-full rounded-md border border-border bg-white"
                />
              </div>
            )}
            {!report && !reportBusy && (
              <p className="text-[11px] text-muted">
                Choose a language, then generate the report. It summarises the uploaded evidence (photos, FIR, call records,
                forensic notes, CCTV) and can be downloaded as a PDF.
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const LANGUAGES_JOINED = "en · हिंदी · Hinglish";