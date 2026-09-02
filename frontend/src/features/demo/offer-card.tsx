import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import type { DemoOffer } from "@/lib/types"
import { verdictMeta } from "./demo-verdict"

interface OfferCardProps {
  offer: DemoOffer
  index: number
  active: boolean
  onSelect: () => void
  onHoverChange?: (hovering: boolean) => void
}

/** Eine Angebotskarte: Produkt, Preis, Varianten, arithmetisches Urteil.
 *
 * Reines Anzeige-Markup - Sortierung und Filterung passieren vorher in
 * `demo-verdict.ts`/`DemoPage`, damit hier nichts als DOM-Test verkleidet ist.
 */
export function OfferCard({ offer, index, active, onSelect, onHoverChange }: OfferCardProps) {
  const verdict = verdictMeta(offer.arithmetic)
  const hasVariantTable = offer.variants.length > 1

  return (
    <article
      role="button"
      tabIndex={0}
      aria-pressed={active}
      onClick={onSelect}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect()}
      onMouseEnter={() => onHoverChange?.(true)}
      onMouseLeave={() => onHoverChange?.(false)}
      className={cn(
        "cursor-pointer space-y-2 rounded-lg border-2 p-3 text-sm transition-colors",
        active ? "border-primary bg-primary/5" : "border-foreground/15 bg-card hover:border-foreground/40",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-semibold">{offer.product ?? "(ohne Produktname)"}</p>
          {offer.brand && <p className="text-xs text-muted-foreground">{offer.brand}</p>}
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <span
              className={cn(
                "shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest",
                verdict.tone,
              )}
            >
              {verdict.label}
            </span>
          </TooltipTrigger>
          <TooltipContent>{verdict.hint}</TooltipContent>
        </Tooltip>
      </div>

      <div className="flex flex-wrap items-baseline gap-2">
        {offer.price && <span className="text-lg font-bold tabular-nums">{offer.price} €</span>}
        {offer.old_price && (
          <span className="text-sm text-muted-foreground line-through tabular-nums">
            {offer.old_price} €
          </span>
        )}
        {offer.discount && (
          <span className="rounded-full bg-[color:var(--riso-pink)]/15 px-2 py-0.5 font-mono text-[10px] text-[color:var(--riso-pink)]">
            {offer.discount}
          </span>
        )}
        {offer.app_price && (
          <span className="rounded-full bg-[color:var(--riso-blue)]/15 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[color:var(--riso-blue)]">
            App {offer.app_price} €
          </span>
        )}
      </div>

      {(offer.quantity || offer.unit_price) && (
        <p className="text-xs text-muted-foreground">
          {offer.quantity}
          {offer.quantity && offer.unit_price && " · "}
          {offer.unit_price && `${offer.unit_price} Grundpreis`}
        </p>
      )}

      {offer.valid && <p className="text-xs text-muted-foreground">Gültig: {offer.valid}</p>}

      {hasVariantTable && (
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="text-muted-foreground">
              <th className="text-left font-normal">Menge</th>
              <th className="text-right font-normal">Preis</th>
            </tr>
          </thead>
          <tbody>
            {offer.variants.map((variant) => (
              <tr key={variant.position} className="border-t border-foreground/10">
                <td className="py-1">{variant.quantity ?? "–"}</td>
                <td className="py-1 text-right tabular-nums">
                  {variant.price ? `${variant.price} €` : "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {offer.confidence != null && (
        <div className="flex items-center gap-2" aria-label={`Konfidenz ${Math.round(offer.confidence * 100)} %`}>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-[color:var(--riso-blue)]"
              style={{ width: `${Math.round(offer.confidence * 100)}%` }}
            />
          </div>
          <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
            {Math.round(offer.confidence * 100)}%
          </span>
        </div>
      )}

      <p className="font-mono text-[10px] text-muted-foreground/60">
        Angebot {index + 1} · Seite {offer.page_index + 1}
      </p>
    </article>
  )
}
