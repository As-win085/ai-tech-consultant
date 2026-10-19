import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { FileJson, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { TranscriptCreatePayload } from "@/api/meeting";
import type { TranscriptSegment } from "@/types/meeting";

const ingestSchema = z.object({
  project_id: z.string().trim().min(1, "Project ID is required."),
  transcript_id: z.string().trim().min(1, "Transcript ID is required."),
  title: z.string().optional(),
  text: z.string().optional(),
});

type IngestForm = z.infer<typeof ingestSchema>;

interface ParsedFile {
  segments?: TranscriptSegment[];
  participants?: TranscriptCreatePayload["participants"];
  text?: string;
}

export function TranscriptIngest({
  onIngest,
  ingesting,
  defaultProjectId,
}: {
  onIngest: (payload: TranscriptCreatePayload) => void;
  ingesting: boolean;
  defaultProjectId?: string;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [parsed, setParsed] = useState<ParsedFile | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const form = useForm<IngestForm>({
    resolver: zodResolver(ingestSchema),
    defaultValues: {
      project_id: defaultProjectId ?? "brightpath-directory",
      transcript_id: "mtg-001-kickoff",
      title: "Brightpath Directory — Project Kickoff",
      text: "",
    },
  });

  const handleFile = async (file: File) => {
    setFileError(null);
    setFileName(file.name);
    try {
      const raw = await file.text();
      const json = JSON.parse(raw) as ParsedFile & { project_id?: string; transcript_id?: string; title?: string };
      if (Array.isArray(json.segments)) {
        setParsed({ segments: json.segments, participants: json.participants });
        // Prefill identity fields from the file when present.
        if (json.project_id) form.setValue("project_id", json.project_id);
        if (json.transcript_id) form.setValue("transcript_id", json.transcript_id);
        if (json.title) form.setValue("title", json.title);
      } else if (typeof json.text === "string") {
        setParsed({ text: json.text });
        form.setValue("text", json.text);
      } else {
        setFileError("The selected JSON has neither a `segments` array nor a `text` string.");
        setParsed(null);
      }
    } catch {
      setFileError("Could not parse that file as JSON.");
      setParsed(null);
    }
  };

  const onSubmit = form.handleSubmit((values) => {
    const payload: TranscriptCreatePayload = {
      project_id: values.project_id.trim(),
      transcript_id: values.transcript_id.trim(),
      title: values.title?.trim() || undefined,
    };
    if (parsed?.segments && parsed.segments.length > 0) {
      payload.segments = parsed.segments;
      if (parsed.participants) payload.participants = parsed.participants;
    } else if (values.text && values.text.trim()) {
      payload.text = values.text.trim();
    }
    onIngest(payload);
  });

  const hasSource = Boolean(parsed?.segments?.length || form.watch("text")?.trim());

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="project_id">Project ID</Label>
          <Input id="project_id" {...form.register("project_id")} />
          {form.formState.errors.project_id && (
            <p className="text-xs text-destructive">{form.formState.errors.project_id.message}</p>
          )}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="transcript_id">Transcript ID</Label>
          <Input id="transcript_id" {...form.register("transcript_id")} />
          {form.formState.errors.transcript_id && (
            <p className="text-xs text-destructive">{form.formState.errors.transcript_id.message}</p>
          )}
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="title">Title</Label>
        <Input id="title" {...form.register("title")} />
      </div>

      <div className="space-y-1.5">
        <Label>Transcript file (optional JSON — read in-browser, then sent as content)</Label>
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleFile(f);
            }}
          />
          <Button type="button" variant="outline" size="sm" onClick={() => fileRef.current?.click()}>
            <Upload className="size-4" /> Choose JSON
          </Button>
          {fileName && (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <FileJson className="size-3.5" /> {fileName}
            </span>
          )}
        </div>
        {fileError && <p className="text-xs text-destructive">{fileError}</p>}
        {parsed?.segments && (
          <p className="text-xs text-success">Loaded {parsed.segments.length} segments from file.</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="text">…or paste labelled transcript text</Label>
        <Textarea
          id="text"
          rows={4}
          placeholder="Dana: We need to support up to 50,000 members.&#10;Marcus: Our directory struggles at a few hundred concurrent users."
          {...form.register("text")}
        />
        <p className="text-xs text-muted-foreground">
          The backend parses either a JSON `segments` array or labelled `Speaker: text` lines. Re-ingesting identical content is idempotent.
        </p>
      </div>

      {!hasSource && (
        <Alert variant="warning">
          <AlertTitle>No transcript content</AlertTitle>
          <AlertDescription>Provide a JSON file or paste transcript text before ingesting.</AlertDescription>
        </Alert>
      )}

      <Button type="submit" loading={ingesting} disabled={!hasSource}>
        Ingest &amp; extract requirements
      </Button>
    </form>
  );
}
