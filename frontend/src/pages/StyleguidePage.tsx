import { Logo } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useTheme } from "@/lib/theme";

export function StyleguidePage() {
  const { theme, setTheme, resolved } = useTheme();

  return (
    <div className="mx-auto max-w-3xl space-y-10 px-4 py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Styleguide — ArtistAssist</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tokens, logo, and core components. Theme: {theme} → {resolved}.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Logo</h2>
        <div className="flex flex-wrap items-end gap-6">
          <Logo variant="mark" className="size-4" />
          <Logo variant="mark" className="size-8" />
          <Logo variant="accent" className="size-10" />
          <Logo variant="full" />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Colors</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ["background", "bg-background border"],
            ["foreground", "bg-foreground"],
            ["primary / vermilion", "bg-primary"],
            ["muted", "bg-muted"],
            ["secondary", "bg-secondary"],
            ["border", "bg-border"],
            ["destructive", "bg-destructive"],
            ["card", "bg-card border"],
          ].map(([label, cls]) => (
            <div key={label} className="space-y-1">
              <div className={`h-12 rounded-md ${cls}`} />
              <p className="text-xs text-muted-foreground">{label}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Buttons</h2>
        <div className="flex flex-wrap gap-2">
          <Button type="button">Primary</Button>
          <Button type="button" variant="secondary">
            Secondary
          </Button>
          <Button type="button" variant="outline">
            Outline
          </Button>
          <Button type="button" variant="ghost">
            Ghost
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" onClick={() => setTheme("system")}>
            System
          </Button>
          <Button type="button" size="sm" onClick={() => setTheme("light")}>
            Light
          </Button>
          <Button type="button" size="sm" onClick={() => setTheme("dark")}>
            Dark
          </Button>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">States</h2>
        <LoadingState />
        <EmptyState title="Empty" description="Designed empty state." />
        <ErrorState title="Error" description="Designed error state." />
      </section>

      <section className="space-y-2 text-sm text-muted-foreground">
        <h2 className="text-sm font-medium text-foreground">Contrast (WCAG AA)</h2>
        <p>
          Light: foreground on background ≈ near-black on near-white (≥7:1). Primary vermilion
          (#FF4D2E-class OKLCH) on white for large text / buttons with white label.
        </p>
        <p>
          Dark: near-white on near-black (≥7:1). Vermilion lightened slightly for primary actions.
        </p>
      </section>
    </div>
  );
}
