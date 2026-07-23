import { useQuery } from "@tanstack/react-query"
import { FileDown, ScanText, Tags, TerminalSquare } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import { nextStep } from "./next-step"

function StatCard({ label, value, icon: Icon }: { label: string; value: number; icon: LucideIcon }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Icon className="size-4" /> {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <span className="text-3xl font-semibold tabular-nums">{value}</span>
      </CardContent>
    </Card>
  )
}

export function OverviewPage() {
  const { data, isPending, isError, error } = useQuery({ queryKey: ["status"], queryFn: api.status })

  if (isPending) return <Skeleton className="h-40 w-full" />
  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Backend nicht erreichbar</AlertTitle>
        <AlertDescription>
          {error.message} — läuft <code>uvicorn magda.api:app --reload</code>?
        </AlertDescription>
      </Alert>
    )
  }

  const step = nextStep(data.totals)

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Pipeline-Übersicht</h1>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Heruntergeladen" value={data.totals.raw} icon={FileDown} />
        <StatCard label="Extrahiert" value={data.totals.words} icon={ScanText} />
        <StatCard label="Gelabelt" value={data.totals.labeled} icon={Tags} />
      </div>

      {step && (
        <Alert>
          <TerminalSquare className="size-4" />
          <AlertTitle>Nächster Schritt</AlertTitle>
          <AlertDescription>
            <code className="font-mono text-sm">{step}</code> (aus dem Projektroot)
          </AlertDescription>
        </Alert>
      )}

      {data.catalogs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Kataloge</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Katalog</TableHead>
                  <TableHead className="text-right">Seiten</TableHead>
                  <TableHead className="text-right">Extrahiert</TableHead>
                  <TableHead className="text-right">Gelabelt</TableHead>
                  <TableHead className="w-[30%]">Fortschritt</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.catalogs.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-mono">{c.id}</TableCell>
                    <TableCell className="text-right tabular-nums">{c.raw}</TableCell>
                    <TableCell className="text-right tabular-nums">{c.words}</TableCell>
                    <TableCell className="text-right tabular-nums">{c.labeled}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress value={c.raw > 0 ? (c.labeled / c.raw) * 100 : 0} />
                        <span className="w-10 text-right font-mono text-xs text-muted-foreground tabular-nums">
                          {c.raw > 0 ? Math.round((c.labeled / c.raw) * 100) : 0}%
                        </span>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
