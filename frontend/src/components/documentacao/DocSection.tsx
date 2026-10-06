import type { ReactNode } from "react"

interface DocSectionProps {
  titulo: string
  children: ReactNode
}

export function DocSection({ titulo, children }: DocSectionProps) {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
      <div className="doc-content space-y-4 text-sm leading-relaxed text-foreground">
        {children}
      </div>
    </div>
  )
}

export function DocH2({ children }: { children: ReactNode }) {
  return (
    <h2 className="pt-2 text-lg font-semibold tracking-tight">{children}</h2>
  )
}

export function DocP({ children }: { children: ReactNode }) {
  return <p className="text-muted-foreground">{children}</p>
}

export function DocList({ children }: { children: ReactNode }) {
  return (
    <ul className="list-disc space-y-1.5 pl-5 text-muted-foreground">
      {children}
    </ul>
  )
}

export function DocCallout({
  children,
  variante = "info",
}: {
  children: ReactNode
  variante?: "info" | "warning"
}) {
  return (
    <div
      className={
        variante === "warning"
          ? "rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm"
          : "rounded-lg border border-info/40 bg-info/10 p-3 text-sm"
      }
    >
      {children}
    </div>
  )
}

export function DocCode({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
      {children}
    </code>
  )
}
