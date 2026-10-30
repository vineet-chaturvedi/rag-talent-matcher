import { Construction } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Placeholder for pages that later steps build. Static (no data), so it is part of the instant shell. */
export function ComingSoon({ step, items }: { step: number; items: readonly string[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Construction className="size-4 text-muted-foreground" aria-hidden />
          Coming in Step {step}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted-foreground">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
